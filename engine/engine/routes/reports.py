from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from engine.config import REPORTS_DIR

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("")
async def list_reports():
    if not REPORTS_DIR.exists():
        return JSONResponse([])

    files = sorted(REPORTS_DIR.glob("*.json"), reverse=True)
    reports = []

    for f in files[:50]:
        try:
            data = json.loads(f.read_text())
            result = data.get("result", {})
            reports.append({
                "filename": f.name,
                "testId": result.get("testId"),
                "testName": result.get("testName"),
                "passed": result.get("passed"),
                "timestamp": result.get("timestamp"),
                "totalDuration": result.get("totalDuration"),
                "healedCount": result.get("healedCount"),
                "stepCount": len(result.get("steps", [])),
            })
        except Exception:
            continue

    return JSONResponse(reports)


@router.get("/{filename}")
async def get_report(filename: str):
    import re
    safe = re.sub(r"[^a-zA-Z0-9._-]", "", filename)
    filepath = REPORTS_DIR / safe
    if not filepath.exists():
        raise HTTPException(404, "Report not found")
    return JSONResponse(json.loads(filepath.read_text()))
