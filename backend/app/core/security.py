from fastapi import Header, HTTPException, Query, status
from typing import Optional
from .config import settings

async def verify_session_token(
    x_session_token: Optional[str] = Header(None),
    token: Optional[str] = Query(None)
):
    """
    Enforce session token validation between Electron desktop and local FastAPI.
    If CLIPFORGE_SESSION_TOKEN is set, requests must supply a matching token.
    """
    expected = settings.SESSION_TOKEN
    if not expected:
        # Development mode without explicit Electron session
        return True

    supplied = x_session_token or token
    if not supplied or supplied != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing desktop session authentication token."
        )
    return True
