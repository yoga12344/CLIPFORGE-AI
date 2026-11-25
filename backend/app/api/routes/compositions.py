"""
ClipForge AI - Composition REST API Endpoints
Provides composition CRUD, immutable version history, OCC conflict detection, and asset management.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.security import verify_session_token
from ...db.models import CompositionAsset, Project
from ...composition.schemas.composition import CompositionSpec
from ...composition.schemas.validation import CompositionValidationResult
from ...composition.services.composition_service import (
    CompositionService,
    CompositionNotFoundError,
    ResourceOwnershipError,
)
from ...composition.services.composition_version_service import (
    CompositionVersionService,
    VersionConflictError,
    ImmutableVersionError,
)
from ...composition.services.composition_validation_service import CompositionValidationService
from ...composition.planner import CompositionPlannerService, CompositionPlanningError
from ...schemas.composition_api_schemas import (
    CreateCompositionRequest,
    AutoPlanCompositionRequest,
    UpdateCompositionRequest,
    CreateVersionRequest,
    RestoreVersionRequest,
    CompositionResponse,
    CompositionVersionResponse,
    RegisterAssetRequest,
    CompositionAssetResponse,
)

router = APIRouter(prefix="/compositions", tags=["Compositions"])


def _format_version_response(v) -> CompositionVersionResponse:
    """Helper to convert CompositionVersion model to response schema."""
    spec = CompositionSpec.model_validate(v.spec_json)
    return CompositionVersionResponse(
        id=v.id,
        composition_id=v.composition_id,
        version_number=v.version_number,
        schema_version=v.schema_version,
        content_hash=v.content_hash,
        change_summary=v.change_summary,
        is_draft=v.is_draft,
        created_at=v.created_at,
        spec=spec,
    )


def _format_composition_response(c, active_v=None) -> CompositionResponse:
    """Helper to convert Composition model to response schema."""
    active_resp = _format_version_response(active_v) if active_v else None
    return CompositionResponse(
        id=c.id,
        project_id=c.project_id,
        source_video_id=c.source_video_id,
        candidate_id=c.candidate_id,
        title=c.title,
        description=c.description,
        status=c.status,
        current_version_id=c.current_version_id,
        created_at=c.created_at,
        updated_at=c.updated_at,
        active_version=active_resp,
    )


# --- Composition CRUD ---

@router.post("", response_model=CompositionResponse, status_code=status.HTTP_201_CREATED)
async def create_composition(
    data: CreateCompositionRequest,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token),
):
    """
    Create a new composition and seed initial Version 1 snapshot.
    """
    try:
        comp, version = await CompositionService.create_composition(
            db=db,
            project_id=data.project_id,
            video_id=data.video_id,
            title=data.title,
            description=data.description,
            candidate_id=data.candidate_id,
            initial_spec=data.initial_spec,
            aspect_ratio=data.aspect_ratio,
        )
        return _format_composition_response(comp, version)
    except ResourceOwnershipError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create composition: {e}")


@router.post("/auto-plan", response_model=CompositionResponse, status_code=status.HTTP_201_CREATED)
async def auto_plan_composition(
    data: AutoPlanCompositionRequest,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token),
):
    """
    Intelligently auto-plan a CompositionSpec from a HighlightCandidate or custom time range.
    Fuses active speaker, diarization, and face tracking signals to generate camera keyframes.
    """
    try:
        if data.candidate_id:
            comp, version, _ = await CompositionPlannerService.plan_composition_for_candidate(
                db=db,
                candidate_id=data.candidate_id,
                project_id=data.project_id,
                aspect_ratio=data.aspect_ratio,
                subtitle_preset=data.subtitle_preset,
                enable_subtitles=data.enable_subtitles,
            )
        elif data.video_id and data.start_time is not None and data.end_time is not None:
            comp, version, _ = await CompositionPlannerService.plan_composition_for_range(
                db=db,
                video_id=data.video_id,
                project_id=data.project_id,
                start_time=data.start_time,
                end_time=data.end_time,
                title=data.title or "Auto-Planned Composition",
                description=data.description,
                aspect_ratio=data.aspect_ratio,
                subtitle_preset=data.subtitle_preset,
                enable_subtitles=data.enable_subtitles,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either candidate_id or (video_id, start_time, end_time) must be provided."
            )
        return _format_composition_response(comp, version)
    except HTTPException:
        raise
    except (CompositionPlanningError, ResourceOwnershipError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Auto-planning failed: {e}")


@router.get("", response_model=List[CompositionResponse])
async def list_compositions(
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token),
):
    """List compositions with optional filtering."""
    comps = await CompositionService.list_compositions(
        db=db,
        project_id=project_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return [_format_composition_response(c) for c in comps]


@router.get("/{composition_id}", response_model=CompositionResponse)
async def get_composition(
    composition_id: str,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token),
):
    """Get composition details with active version specification."""
    res = await CompositionService.get_composition_with_version(db, composition_id)
    if not res:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Composition '{composition_id}' not found")
    comp, version, _ = res
    return _format_composition_response(comp, version)


@router.patch("/{composition_id}", response_model=CompositionResponse)
async def update_composition_metadata(
    composition_id: str,
    data: UpdateCompositionRequest,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token),
):
    """Update mutable metadata on composition container (title, description, status)."""
    try:
        updated = await CompositionService.update_composition_metadata(
            db=db,
            composition_id=composition_id,
            title=data.title,
            description=data.description,
            status=data.status,
        )
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Composition '{composition_id}' not found")
        
        # Fetch active version for response
        res = await CompositionService.get_composition_with_version(db, composition_id)
        active_v = res[1] if res else None
        return _format_composition_response(updated, active_v)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{composition_id}")
async def delete_composition(
    composition_id: str,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token),
):
    """Delete composition and cascade-delete all versions, renders, and artifacts."""
    deleted = await CompositionService.delete_composition(db, composition_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Composition '{composition_id}' not found")
    return {"success": True, "composition_id": composition_id}


# --- Composition Versions & OCC ---

@router.post("/{composition_id}/versions", response_model=CompositionVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_composition_version(
    composition_id: str,
    data: CreateVersionRequest,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token),
):
    """
    Create a new immutable version snapshot for a composition.
    Enforces Optimistic Concurrency Control (OCC) if expected_version_number is specified.
    """
    comp = await CompositionService.get_composition(db, composition_id)
    if not comp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Composition '{composition_id}' not found")

    # Ensure spec IDs align with composition
    data.spec.composition_id = comp.id
    data.spec.project_id = comp.project_id
    data.spec.source_video_id = comp.source_video_id

    try:
        version = await CompositionVersionService.create_version(
            db=db,
            composition=comp,
            spec=data.spec,
            change_summary=data.change_summary,
            is_draft=data.is_draft,
            expected_version_number=data.expected_version_number,
        )
        return _format_version_response(version)
    except VersionConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to create version: {e}")


@router.get("/{composition_id}/versions", response_model=List[CompositionVersionResponse])
async def list_composition_versions(
    composition_id: str,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token),
):
    """List all version history records for a composition."""
    comp = await CompositionService.get_composition(db, composition_id)
    if not comp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Composition '{composition_id}' not found")

    versions = await CompositionVersionService.list_versions(db, composition_id)
    return [_format_version_response(v) for v in versions]


@router.get("/{composition_id}/versions/{version_number}", response_model=CompositionVersionResponse)
async def get_composition_version(
    composition_id: str,
    version_number: int,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token),
):
    """Fetch an exact historical version snapshot."""
    v = await CompositionVersionService.get_version(db, composition_id, version_number)
    if not v:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_number} of composition '{composition_id}' not found"
        )
    return _format_version_response(v)


@router.post("/{composition_id}/versions/{version_number}/restore", response_model=CompositionVersionResponse)
async def restore_composition_version(
    composition_id: str,
    version_number: int,
    data: RestoreVersionRequest = RestoreVersionRequest(),
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token),
):
    """
    Non-destructive restore: Restores historical version N by creating a new version snapshot
    with N's specification payload.
    """
    comp = await CompositionService.get_composition(db, composition_id)
    if not comp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Composition '{composition_id}' not found")

    try:
        new_v = await CompositionVersionService.restore_version(
            db=db,
            composition=comp,
            target_version_number=version_number,
            description=data.description,
        )
        return _format_version_response(new_v)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Restore failed: {e}")


# --- Validation Endpoint ---

@router.post("/{composition_id}/validate", response_model=CompositionValidationResult)
async def validate_composition(
    composition_id: str,
    spec_override: Optional[CompositionSpec] = None,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token),
):
    """
    Validates a composition specification against project assets and internal semantics
    without triggering a render.
    """
    comp = await CompositionService.get_composition(db, composition_id)
    if not comp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Composition '{composition_id}' not found")

    if spec_override is not None:
        target_spec = spec_override
    else:
        res = await CompositionService.get_composition_with_version(db, composition_id)
        if not res:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active version spec found")
        target_spec = res[2]

    # Ensure IDs align
    target_spec.composition_id = comp.id
    target_spec.project_id = comp.project_id
    target_spec.source_video_id = comp.source_video_id

    result = await CompositionValidationService.validate_spec(db, target_spec)
    return result


# --- Project Composition Assets ---

@router.post("/projects/{project_id}/assets", response_model=CompositionAssetResponse, status_code=status.HTTP_201_CREATED)
async def register_project_asset(
    project_id: str,
    data: RegisterAssetRequest,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token),
):
    """
    Registers a local media asset (B-roll, music, logo) into a project's composition namespace.
    """
    # Verify project
    p_res = await db.execute(select(Project).where(Project.id == project_id))
    if not p_res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found")

    # Check for duplicate logical_asset_id within project and type
    existing_res = await db.execute(
        select(CompositionAsset).where(
            CompositionAsset.project_id == project_id,
            CompositionAsset.asset_type == data.asset_type,
            CompositionAsset.logical_asset_id == data.logical_asset_id,
        )
    )
    if existing_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Asset with ID '{data.logical_asset_id}' and type '{data.asset_type}' already exists in project."
        )

    asset = CompositionAsset(
        project_id=project_id,
        asset_type=data.asset_type,
        logical_asset_id=data.logical_asset_id,
        name=data.name.strip(),
        file_path=data.file_path.strip(),
        file_size_bytes=data.file_size_bytes,
        duration_seconds=data.duration_seconds,
        media_metadata=data.media_metadata,
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)

    return CompositionAssetResponse(
        id=asset.id,
        project_id=asset.project_id,
        asset_type=asset.asset_type,
        logical_asset_id=asset.logical_asset_id,
        asset_uri=f"asset://{asset.asset_type}/{asset.logical_asset_id}",
        name=asset.name,
        file_size_bytes=asset.file_size_bytes,
        duration_seconds=asset.duration_seconds,
        media_metadata=asset.media_metadata,
        created_at=asset.created_at,
    )


@router.get("/projects/{project_id}/assets", response_model=List[CompositionAssetResponse])
async def list_project_assets(
    project_id: str,
    asset_type: Optional[str] = Query(None, description="Optional type filter (videos, audio, broll, images)"),
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token),
):
    """List all registered composition assets for a project."""
    stmt = select(CompositionAsset).where(CompositionAsset.project_id == project_id)
    if asset_type:
        stmt = stmt.where(CompositionAsset.asset_type == asset_type)
    stmt = stmt.order_by(desc(CompositionAsset.created_at))

    res = await db.execute(stmt)
    assets = res.scalars().all()

    return [
        CompositionAssetResponse(
            id=a.id,
            project_id=a.project_id,
            asset_type=a.asset_type,
            logical_asset_id=a.logical_asset_id,
            asset_uri=f"asset://{a.asset_type}/{a.logical_asset_id}",
            name=a.name,
            file_size_bytes=a.file_size_bytes,
            duration_seconds=a.duration_seconds,
            media_metadata=a.media_metadata,
            created_at=a.created_at,
        )
        for a in assets
    ]


# =============================================================================
# PHASE 9 STAGE 3: RENDER GRAPH & EXECUTION ROUTES
# =============================================================================

from ...composition.render.services.render_plan_service import RenderPlanService
from ...composition.render.services.render_service import RenderService
from ...schemas.composition_api_schemas import (
    CompileExecutionPlanRequest,
    CompileExecutionPlanResponse,
    CreateRenderRequest,
    CompositionRenderResponse,
    RenderArtifactResponse,
)


def _format_render_response(r, artifacts=None) -> CompositionRenderResponse:
    art_list = []
    if artifacts:
        art_list = [
            RenderArtifactResponse(
                id=a.id,
                composition_render_id=a.composition_render_id,
                artifact_type=a.artifact_type,
                file_path=a.file_path,
                file_size_bytes=a.file_size_bytes,
                created_at=a.created_at,
            )
            for a in artifacts
        ]
    return CompositionRenderResponse(
        id=r.id,
        composition_id=r.composition_id,
        composition_version_id=r.composition_version_id,
        job_id=r.job_id,
        output_path=r.output_path,
        status=r.status,
        progress_percent=r.progress_percent,
        error_message=r.error_message,
        render_duration_seconds=r.render_duration_seconds,
        file_size_bytes=r.file_size_bytes,
        validation_metrics=r.validation_metrics,
        created_at=r.created_at,
        completed_at=r.completed_at,
        artifacts=art_list,
    )


@router.post(
    "/{composition_id}/versions/{version_id}/compile",
    response_model=CompileExecutionPlanResponse,
    summary="Compile composition version into an FFmpeg execution plan without rendering",
)
async def compile_composition_plan(
    composition_id: str,
    version_id: str,
    req: Optional[CompileExecutionPlanRequest] = None,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token),
):
    """Compile an immutable CompositionVersion into an explicit FFmpeg argument array and filtergraph."""
    try:
        preferred = req.preferred_encoder if req else None
        plan_dict = await RenderPlanService.generate_plan(
            composition_id=composition_id,
            version_id=version_id,
            db=db,
            preferred_encoder=preferred,
        )
        return CompileExecutionPlanResponse(**plan_dict)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Compilation failed: {str(e)}")


@router.post(
    "/{composition_id}/versions/{version_id}/renders",
    response_model=CompositionRenderResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue background composition render",
)
async def create_composition_render(
    composition_id: str,
    version_id: str,
    req: Optional[CreateRenderRequest] = None,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token),
):
    """Queue a persistent composition render using JobManager."""
    try:
        out_path = req.custom_output_path if req else None
        render = await RenderService.create_render(
            composition_id=composition_id,
            version_id=version_id,
            db=db,
            custom_output_path=out_path,
        )
        return _format_render_response(render)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to queue render: {str(e)}")


@router.get(
    "/{composition_id}/renders",
    response_model=List[CompositionRenderResponse],
    summary="List renders for a composition",
)
async def list_composition_renders(
    composition_id: str,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token),
):
    """List all renders associated with a composition."""
    renders = await RenderService.list_renders_for_composition(composition_id, db)
    return [_format_render_response(r) for r in renders]


@router.get(
    "/{composition_id}/renders/{render_id}",
    response_model=CompositionRenderResponse,
    summary="Get render status and details",
)
async def get_composition_render(
    composition_id: str,
    render_id: str,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token),
):
    """Fetch status, metrics, and duration of a composition render."""
    render = await RenderService.get_render(render_id, db)
    if not render or render.composition_id != composition_id:
        raise HTTPException(status_code=404, detail=f"Render '{render_id}' not found.")
    artifacts = await RenderService.get_artifacts_for_render(render_id, db)
    return _format_render_response(render, artifacts)


@router.post(
    "/{composition_id}/renders/{render_id}/cancel",
    summary="Cancel active composition render",
)
async def cancel_composition_render(
    composition_id: str,
    render_id: str,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token),
):
    """Cancel an ongoing composition render."""
    success = await RenderService.cancel_render(render_id, db)
    if not success:
        raise HTTPException(status_code=400, detail="Render cannot be cancelled or was not found.")
    return {"message": f"Render '{render_id}' cancelled successfully.", "render_id": render_id}


@router.get(
    "/{composition_id}/renders/{render_id}/artifacts",
    response_model=List[RenderArtifactResponse],
    summary="Get artifacts for a render",
)
async def get_render_artifacts(
    composition_id: str,
    render_id: str,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_session_token),
):
    """Fetch generated scripts and sidecar files for a render."""
    render = await RenderService.get_render(render_id, db)
    if not render or render.composition_id != composition_id:
        raise HTTPException(status_code=404, detail=f"Render '{render_id}' not found.")
    artifacts = await RenderService.get_artifacts_for_render(render_id, db)
    return [
        RenderArtifactResponse(
            id=a.id,
            composition_render_id=a.composition_render_id,
            artifact_type=a.artifact_type,
            file_path=a.file_path,
            file_size_bytes=a.file_size_bytes,
            created_at=a.created_at,
        )
        for a in artifacts
    ]
