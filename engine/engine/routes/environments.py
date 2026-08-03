from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from engine.core.environments import (
    delete_environment,
    load_environments,
    upsert_environment,
)

router = APIRouter(prefix="/api/environments", tags=["environments"])


@router.get("")
async def list_environments():
    return JSONResponse(load_environments())


@router.put("/{key}")
async def put_environment(key: str, request: Request):
    body = await request.json()
    name = body.get("name", key.title())
    base_url = body.get("baseUrl", "")
    if not base_url:
        return JSONResponse({"error": "baseUrl is required"}, status_code=400)
    envs = upsert_environment(key, name, base_url)
    return JSONResponse(envs)


@router.delete("/{key}")
async def remove_environment(key: str):
    envs = delete_environment(key)
    return JSONResponse(envs)
