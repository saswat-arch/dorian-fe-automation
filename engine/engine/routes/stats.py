from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from engine.config import INTENTS_DIR, REPORTS_DIR

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
async def get_stats():
    intent_count = 0
    if INTENTS_DIR.exists():
        intent_count = len(list(INTENTS_DIR.glob("*.json")))

    report_count = 0
    pass_count = 0
    last_run_at = None
    last_run_passed = None
    total_healed = 0

    if REPORTS_DIR.exists():
        files = sorted(REPORTS_DIR.glob("*.json"), reverse=True)
        report_count = len(files)

        for f in files[:10]:
            try:
                data = json.loads(f.read_text())
                result = data.get("result", {})
                if result.get("passed"):
                    pass_count += 1
                total_healed += result.get("healedCount", 0)
            except Exception:
                continue

        if files:
            try:
                data = json.loads(files[0].read_text())
                last_run_at = data.get("result", {}).get("timestamp")
                last_run_passed = data.get("result", {}).get("passed")
            except Exception:
                pass

    pass_rate = round((pass_count / min(report_count, 10)) * 100) if report_count > 0 else None

    return JSONResponse({
        "intentCount": intent_count,
        "reportCount": report_count,
        "passRate": pass_rate,
        "lastRunAt": last_run_at,
        "lastRunPassed": last_run_passed,
        "totalHealed": total_healed,
    })
