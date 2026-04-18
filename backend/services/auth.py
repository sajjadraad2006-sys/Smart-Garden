"""API Key authentication for write endpoints.

A-10 FIX: POST /api/control/relay had no auth — anyone on the local
network could fire irrigation pumps or pH dosing. This adds simple
API key auth via X-API-Key header for all write endpoints.
Read endpoints (GET) stay open for the dashboard.
"""
import os
import logging
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

logger = logging.getLogger("agrimaster.auth")

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# Load from environment variable, with a dev-mode default
_API_KEY = os.environ.get("AGRIMASTER_API_KEY", "changeme-local-dev")


async def require_api_key(api_key: str = Security(API_KEY_HEADER)):
    """Dependency for FastAPI routes that require authentication.
    Apply to all POST, PUT, DELETE endpoints."""
    if not api_key or api_key != _API_KEY:
        logger.warning(f"Unauthorized API access attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Set X-API-Key header."
        )
    return api_key
