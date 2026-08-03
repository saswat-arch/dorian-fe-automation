from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from engine.config import INTENTS_DIR, SUITES_DIR
from engine.core.runner import RunnerOptions, TestRunner
from engine.reporters.json_reporter import write_json_report
from engine.schema.result import RunResult
from engine.schema.suite import Suite, SuiteMetadata
from engine.utils.logger import create_logger

log = create_logger("routes-suites")

router = APIRouter(prefix="/api/suites", tags=["suites"])


PRESET_SUITES: list[dict[str, Any]] = [
    {"id": "suite-smoke", "name": "Smoke", "description": "Critical-path tests to run on every deploy.", "tags": ["preset", "smoke"]},
    {"id": "suite-regression", "name": "Regression", "description": "Full regression pass over historical bug scenarios.", "tags": ["preset", "regression"]},
    {"id": "suite-pr", "name": "PR", "description": "Tests to run on every pull request.", "tags": ["preset", "pr"]},
    {"id": "suite-bugs", "name": "Bugs", "description": "Reproductions for known open bugs.", "tags": ["preset", "bugs"]},
]


def _suite_path(suite_id: str) -> Path:
    return SUITES_DIR / f"{suite_id}.json"


def _load_suite(suite_id: str) -> Suite | None:
    p = _suite_path(suite_id)
    if not p.exists():
        return None
    try:
        return Suite.model_validate(json.loads(p.read_text()))
    except Exception as e:
        log.error(f"Failed to load suite {suite_id}: {e}")
        return None


def _write_suite(suite: Suite) -> None:
    SUITES_DIR.mkdir(parents=True, exist_ok=True)
    _suite_path(suite.id).write_text(json.dumps(suite.model_dump(by_alias=True), indent=2))


def ensure_preset_suites() -> None:
    """Create the four preset suites on first boot if they don't exist yet."""
    SUITES_DIR.mkdir(parents=True, exist_ok=True)
    for preset in PRESET_SUITES:
        if _suite_path(preset["id"]).exists():
            continue
        suite = Suite(
            id=preset["id"],
            name=preset["name"],
            description=preset["description"],
            intent_ids=[],
            tags=preset["tags"],
            is_preset=True,
            run_mode="fail-fast",
        )
        _write_suite(suite)
        log.info(f"Created preset suite: {preset['id']}")


@router.get("")
async def list_suites():
    SUITES_DIR.mkdir(parents=True, exist_ok=True)
    suites: list[dict[str, Any]] = []
    for path in sorted(SUITES_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text())
            suite = Suite.model_validate(data)
            suites.append(suite.model_dump(by_alias=True))
        except Exception as e:
            log.warning(f"Skipping corrupt suite file {path.name}: {e}")
    # Presets first, then alphabetical
    suites.sort(key=lambda s: (not s.get("isPreset"), s.get("name", "").lower()))
    return suites


@router.get("/{suite_id}")
async def get_suite(suite_id: str):
    suite = _load_suite(suite_id)
    if suite is None:
        return JSONResponse({"error": "Suite not found"}, status_code=404)
    return suite.model_dump(by_alias=True)


@router.post("")
async def create_suite(request: Request):
    body = await request.json()
    name = (body.get("name") or "").strip()
    if not name:
        return JSONResponse({"error": "name is required"}, status_code=400)

    suite = Suite(
        id=body.get("id") or f"suite-{uuid.uuid4().hex[:8]}",
        name=name,
        description=body.get("description"),
        intent_ids=body.get("intentIds", []) or [],
        tags=body.get("tags", []) or [],
        is_preset=False,
        run_mode=body.get("runMode", "fail-fast"),
    )
    if _suite_path(suite.id).exists():
        return JSONResponse({"error": f"Suite {suite.id} already exists"}, status_code=409)
    _write_suite(suite)
    return suite.model_dump(by_alias=True)


@router.put("/{suite_id}")
async def update_suite(suite_id: str, request: Request):
    suite = _load_suite(suite_id)
    if suite is None:
        return JSONResponse({"error": "Suite not found"}, status_code=404)

    body = await request.json()
    # Preset suites: allow editing description/intentIds/tags but NOT name or id
    if "name" in body and not suite.is_preset:
        suite.name = body["name"]
    if "description" in body:
        suite.description = body["description"]
    if "intentIds" in body:
        # De-duplicate while preserving order
        seen: set[str] = set()
        ordered: list[str] = []
        for iid in body["intentIds"]:
            if iid not in seen:
                seen.add(iid)
                ordered.append(iid)
        suite.intent_ids = ordered
    if "tags" in body and not suite.is_preset:
        suite.tags = body["tags"]
    if "runMode" in body:
        suite.run_mode = body["runMode"]

    suite.metadata.updated_at = datetime.now(timezone.utc).isoformat()
    _write_suite(suite)
    return suite.model_dump(by_alias=True)


@router.delete("/{suite_id}")
async def delete_suite(suite_id: str):
    suite = _load_suite(suite_id)
    if suite is None:
        return JSONResponse({"error": "Suite not found"}, status_code=404)
    if suite.is_preset:
        return JSONResponse({"error": "Preset suites cannot be deleted"}, status_code=403)
    _suite_path(suite_id).unlink()
    return {"deleted": suite_id}


@router.get("/{suite_id}/events")
async def run_suite_stream(suite_id: str, request: Request):
    suite = _load_suite(suite_id)
    if suite is None:
        return JSONResponse({"error": "Suite not found"}, status_code=404)
    if not suite.intent_ids:
        return JSONResponse({"error": "Suite has no intents to run"}, status_code=400)

    headed = request.query_params.get("headed", "false").lower() != "false"
    env_param = request.query_params.get("env", "") or None
    run_id = f"suite-run-{int(time.time() * 1000)}"

    async def generate():
        yield {"event": "suite:start", "data": json.dumps({
            "runId": run_id,
            "suiteId": suite.id,
            "suiteName": suite.name,
            "intentIds": suite.intent_ids,
            "runMode": suite.run_mode,
            "environment": env_param,
        })}

        total_pass = 0
        total_fail = 0
        skipped: list[str] = []

        for idx, intent_id in enumerate(suite.intent_ids):
            intent_path = str(INTENTS_DIR / f"{intent_id}.json")
            yield {"event": "test:queued", "data": json.dumps({
                "intentId": intent_id, "index": idx, "total": len(suite.intent_ids),
            })}

            if not Path(intent_path).exists():
                yield {"event": "test:error", "data": json.dumps({
                    "intentId": intent_id, "error": "Intent file not found",
                })}
                total_fail += 1
                if suite.run_mode == "fail-fast":
                    skipped = suite.intent_ids[idx + 1:]
                    break
                continue

            try:
                options = RunnerOptions(browser="chromium", headed=headed, environment=env_param)
                runner = TestRunner(options)
                final_result: dict[str, Any] | None = None
                async for event in runner.run_intent_streaming(intent_path):
                    name = event["event"]
                    if name == "run:complete":
                        final_result = event["data"]
                        yield {"event": "test:complete", "data": json.dumps({
                            "intentId": intent_id, "result": final_result,
                        })}
                    else:
                        yield {"event": name, "data": json.dumps(event["data"])}

                if final_result:
                    result = RunResult.model_validate(final_result)
                    await write_json_report(result)
                    if result.passed:
                        total_pass += 1
                    else:
                        total_fail += 1
                        if suite.run_mode == "fail-fast":
                            skipped = suite.intent_ids[idx + 1:]
                            for skipped_id in skipped:
                                yield {"event": "test:skipped", "data": json.dumps({
                                    "intentId": skipped_id,
                                    "reason": f"Fail-fast: {intent_id} failed",
                                })}
                            break
            except Exception as e:
                log.error(f"Suite run error for {intent_id}: {e}", exc_info=True)
                yield {"event": "test:error", "data": json.dumps({
                    "intentId": intent_id, "error": str(e),
                })}
                total_fail += 1
                if suite.run_mode == "fail-fast":
                    skipped = suite.intent_ids[idx + 1:]
                    for skipped_id in skipped:
                        yield {"event": "test:skipped", "data": json.dumps({
                            "intentId": skipped_id,
                            "reason": f"Fail-fast: {intent_id} errored",
                        })}
                    break

        # Update suite metadata
        try:
            suite.metadata.last_run = datetime.now(timezone.utc).isoformat()
            suite.metadata.run_count += 1
            if total_fail == 0 and total_pass > 0:
                suite.metadata.pass_count += 1
            _write_suite(suite)
        except Exception as e:
            log.warning(f"Failed to update suite metadata: {e}")

        yield {"event": "suite:complete", "data": json.dumps({
            "runId": run_id,
            "suiteId": suite.id,
            "totalIntents": len(suite.intent_ids),
            "passed": total_pass,
            "failed": total_fail,
            "skipped": len(skipped),
            "suitePassed": total_fail == 0 and len(skipped) == 0,
        })}

    return EventSourceResponse(generate())
