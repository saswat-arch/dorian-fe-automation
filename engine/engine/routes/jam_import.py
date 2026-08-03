from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from engine.config import ANTHROPIC_API_KEY, INTENTS_DIR, JAM_ACCESS_TOKEN
from engine.converters.jam_converter import (
    JamAuthError,
    JamFetchError,
    convert_jam_recording,
    fetch_jam_recording,
    save_intent,
)
from engine.utils.logger import create_logger

log = create_logger("routes-jam")

router = APIRouter(prefix="/api/intents/from-jam", tags=["jam"])


@router.post("")
async def import_from_jam(request: Request):
    try:
        body = await request.json()
        jam_url = body.get("jamUrl")
        base_url = body.get("baseUrl")
        test_name = body.get("testName")

        if not jam_url:
            return JSONResponse({"error": "Jam URL is required"}, status_code=400)

        if not JAM_ACCESS_TOKEN:
            return JSONResponse(
                {"error": "JAM_ACCESS_TOKEN not configured. Add JAM_ACCESS_TOKEN=jam_pat_... to your .env file."},
                status_code=500,
            )

        if not ANTHROPIC_API_KEY:
            return JSONResponse({"error": "ANTHROPIC_API_KEY not configured."}, status_code=500)

        log.info(f"Importing Jam recording: {jam_url}")

        try:
            recording = await fetch_jam_recording(jam_url)
        except JamAuthError as e:
            log.error(f"Jam auth failed: {e}")
            return JSONResponse({"error": str(e)}, status_code=401)
        except JamFetchError as e:
            log.error(f"Jam fetch failed: {e}")
            return JSONResponse({"error": str(e)}, status_code=502)

        sources = recording.pop("sources", {})

        log.info(f"Recording fetched. Sources: {sources}")

        try:
            intent = await convert_jam_recording(
                recording,
                base_url=base_url or recording.get("metadata", {}).get("url"),
                test_name=test_name,
            )
        except Exception as e:
            log.error(f"Claude conversion failed: {e}", exc_info=True)
            now = datetime.now(timezone.utc).isoformat()
            test_id = f"test-{uuid.uuid4().hex[:8]}"
            effective_url = base_url or recording.get("metadata", {}).get("url", "http://localhost:3000")
            intent_data = {
                "id": test_id,
                "name": test_name or "Jam Recording (fallback)",
                "description": f"Fallback intent — Claude conversion failed: {e}",
                "baseUrl": effective_url,
                "createdFrom": "recorder",
                "tags": ["converted", "jam", "fallback"],
                "steps": [{"id": "step-1", "order": 1, "type": "navigate", "intent": f"Navigate to {effective_url}", "url": effective_url}],
                "assertions": [{"id": "assert-1", "afterStep": "step-1", "intent": "Verify page loads", "type": "url", "expected": effective_url}],
                "config": {"timeout": 30000, "retries": 1, "viewport": {"width": 1280, "height": 720}, "browsers": ["chromium"]},
                "metadata": {"createdAt": now, "updatedAt": now, "runCount": 0, "passCount": 0, "passRate": 0, "avgDuration": 0, "source": "jam"},
            }
            from engine.schema.intent import TestIntent
            intent = TestIntent.model_validate(intent_data)

        filepath = await save_intent(intent)
        intent_dict = intent.model_dump(by_alias=True)

        log.info(f"Intent saved: {filepath} ({len(intent_dict.get('steps', []))} steps, {len(intent_dict.get('assertions', []))} assertions)")

        return JSONResponse({"intent": intent_dict, "saved": True, "sources": sources})

    except Exception as e:
        log.error(f"Jam import error: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)
