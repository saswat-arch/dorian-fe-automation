from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from engine.config import AUTH_DIR
from engine.core.auth_setup import (
    clear_auth_state,
    get_auth_status,
    load_auth_config,
    run_auth_setup,
    save_auth_config,
)
from engine.utils.logger import create_logger

log = create_logger("routes-auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/status")
async def auth_status(env: Optional[str] = None):
    """Check if auth state exists and is fresh for a given environment."""
    status = get_auth_status(env)
    return JSONResponse(status)


@router.get("/config")
async def auth_config():
    """Return the current auth config."""
    config = load_auth_config()
    return JSONResponse(config)


@router.put("/config")
async def update_auth_config(request: Request):
    """Update the auth config."""
    body = await request.json()
    save_auth_config(body)
    return JSONResponse({"saved": True})


@router.post("/setup")
async def setup_auth(request: Request):
    """Launch interactive auth setup in a separate process (browser opens on your machine)."""
    try:
        body = await request.json() if request.headers.get("content-type") else {}
    except Exception:
        body = {}

    environment = body.get("environment")

    try:
        log.info(f"Starting auth setup (env={environment})")
        result = await run_auth_setup(environment=environment)
        return JSONResponse(result)
    except Exception as e:
        log.error(f"Auth setup failed: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.delete("/state")
async def delete_auth_state(env: Optional[str] = None):
    """Clear saved auth state for a given environment."""
    await clear_auth_state(env)
    return JSONResponse({"cleared": True, "environment": env})


@router.get("")
async def list_auth_states():
    """List all auth state files."""
    if not AUTH_DIR.exists():
        return JSONResponse({"states": []})

    states = []
    for child in AUTH_DIR.iterdir():
        if child.is_dir() and (child / "default.json").exists():
            states.append({"environment": child.name, "filename": "default.json"})
    legacy = AUTH_DIR / "default.json"
    if legacy.exists():
        states.append({"environment": None, "filename": "default.json"})

    return JSONResponse({"states": states})
