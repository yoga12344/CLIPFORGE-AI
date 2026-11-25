"""
ClipForge AI - Render Plan Service
Phase 9 Stage 3: Compiles an immutable CompositionVersion into an execution plan without rendering.
"""

from typing import Any, Dict, Optional
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....db.models import Composition, CompositionVersion, CompositionAsset, Video
from ...schemas.composition import CompositionSpec
from ..graph.graph_builder import CompositionToGraphBuilder
from ..compiler.ffmpeg_compiler import RenderGraphCompiler, FFmpegExecutionPlan


class RenderPlanService:
    """Provides dry-run compilation of a CompositionVersion into an FFmpeg execution plan."""

    @classmethod
    async def generate_plan(
        cls,
        composition_id: str,
        version_id: str,
        db: AsyncSession,
        preferred_encoder: Optional[str] = None,
    ) -> Dict[str, Any]:
        # 1. Fetch version
        v_res = await db.execute(
            select(CompositionVersion).where(
                CompositionVersion.id == version_id,
                CompositionVersion.composition_id == composition_id
            )
        )
        version = v_res.scalar_one_or_none()
        if not version:
            raise ValueError(f"CompositionVersion '{version_id}' not found for composition '{composition_id}'.")

        c_res = await db.execute(select(Composition).where(Composition.id == composition_id))
        composition = c_res.scalar_one_or_none()

        spec = CompositionSpec.model_validate(version.spec_json) if isinstance(version.spec_json, dict) else CompositionSpec.from_canonical_json(version.spec_json)
        delivery = getattr(spec, "delivery_profile", None) or getattr(spec, "delivery", None)

        # 2. Resolve source media
        source_path: str = "placeholder_source.mp4"
        if spec.source_media.asset_uri and composition:
            try:
                from ...schemas.assets import parse_asset_uri
                parsed = parse_asset_uri(spec.source_media.asset_uri)
                a_res = await db.execute(
                    select(CompositionAsset).where(
                        CompositionAsset.project_id == composition.project_id,
                        CompositionAsset.asset_type == parsed.asset_type,
                        CompositionAsset.logical_asset_id == parsed.asset_id,
                    )
                )
                asset = a_res.scalar_one_or_none()
                if asset:
                    source_path = asset.file_path
            except Exception:
                pass

        if source_path == "placeholder_source.mp4" and composition and composition.source_video_id:
            v_media = await db.execute(select(Video).where(Video.id == composition.source_video_id))
            vid = v_media.scalar_one_or_none()
            if vid:
                source_path = vid.file_path

        boundary = getattr(spec, "clip_boundary", None) or getattr(getattr(spec, "timeline", None), "composition_boundary", None)
        start_us = getattr(boundary, "source_start_us", getattr(boundary, "in_point_us", 0)) if boundary else 0
        end_us = getattr(boundary, "source_end_us", getattr(boundary, "out_point_us", 1000000)) if boundary else getattr(getattr(spec, "timeline", None), "total_duration_us", 1000000)
        est_dur_s = (end_us - start_us) / 1_000_000.0

        # 3. Build graph
        graph = CompositionToGraphBuilder.build_graph(
            spec=spec,
            source_media_path=source_path,
            output_file_path=f"output_{composition_id[:8]}.mp4",
        )

        # 4. Compile
        plan: FFmpegExecutionPlan = RenderGraphCompiler.compile(
            graph=graph,
            delivery=delivery,
            render_id=f"plan_{composition_id[:8]}",
            preferred_encoder=preferred_encoder,
            estimated_duration_seconds=est_dur_s,
        )

        return {
            "composition_id": composition_id,
            "version_id": version_id,
            "version_number": version.version_number,
            "video_encoder": plan.video_encoder,
            "command_args": plan.command_args,
            "filter_complex_string": plan.filter_complex_string,
            "is_script_file": plan.is_script_file,
            "input_files": plan.input_files,
            "output_file_path": plan.output_file_path,
            "estimated_duration_seconds": round(est_dur_s, 3),
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
        }
