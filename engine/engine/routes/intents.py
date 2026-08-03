from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from engine.config import INTENTS_DIR

router = APIRouter(prefix="/api/intents", tags=["intents"])


@router.get("")
async def list_intents():
    if not INTENTS_DIR.exists():
        return JSONResponse([])

    intents = []
    for f in sorted(INTENTS_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            intents.append(data)
        except Exception:
            continue

    intents.sort(key=lambda x: x.get("name", ""))
    return JSONResponse(intents)


@router.post("")
async def create_intent(request: Request):
    intent = await request.json()
    if not intent.get("id") or not intent.get("name"):
        raise HTTPException(400, "Missing id or name")

    INTENTS_DIR.mkdir(parents=True, exist_ok=True)
    filepath = INTENTS_DIR / f"{intent['id']}.json"
    filepath.write_text(json.dumps(intent, indent=2))
    return JSONResponse(intent, status_code=201)


@router.get("/{intent_id}")
async def get_intent(intent_id: str):
    filepath = INTENTS_DIR / f"{intent_id}.json"
    if not filepath.exists():
        raise HTTPException(404, "Intent not found")
    return JSONResponse(json.loads(filepath.read_text()))


@router.put("/{intent_id}")
async def update_intent(intent_id: str, request: Request):
    intent = await request.json()
    filepath = INTENTS_DIR / f"{intent_id}.json"
    filepath.write_text(json.dumps(intent, indent=2))
    return JSONResponse(intent)


@router.delete("/{intent_id}")
async def delete_intent(intent_id: str):
    filepath = INTENTS_DIR / f"{intent_id}.json"
    if not filepath.exists():
        raise HTTPException(404, "Intent not found")
    filepath.unlink()
    return JSONResponse({"success": True})
