from __future__ import annotations

import json
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from engine.config import INTENTS_DIR
from engine.core.runner import RunnerOptions, TestRunner
from engine.reporters.json_reporter import write_json_report
from engine.schema.result import RunResult
from engine.utils.logger import create_logger

log = create_logger("routes-run")

router = APIRouter(tags=["run"])


@router.post("/api/run")
async def start_run(request: Request):
    body = await request.json()
    intent_ids = body.get("intentIds", [])
    if not intent_ids:
        return JSONResponse({"error": "No intent IDs provided"}, status_code=400)

    run_id = f"run-{int(time.time() * 1000)}"
    intent_paths = [str(INTENTS_DIR / f"{iid}.json") for iid in intent_ids]

    return JSONResponse({
        "runId": run_id,
        "intentPaths": intent_paths,
        "message": f"Run {run_id} queued with {len(intent_ids)} intent(s)",
    })


@router.get("/api/events")
async def events_stream(request: Request):
    intent_ids_param = request.query_params.get("intentIds", "")
    run_id = request.query_params.get("runId", "")
    headed_param = request.query_params.get("headed", "true")
    env_param = request.query_params.get("env", "") or None

    if not intent_ids_param:
        return JSONResponse({"error": "Missing intentIds"}, status_code=400)

    intent_ids = [x for x in intent_ids_param.split(",") if x]
    headed = headed_param.lower() != "false"

    async def generate():
        yield {"event": "connected", "data": json.dumps({"runId": run_id, "intentIds": intent_ids, "environment": env_param})}

        try:
            for intent_id in intent_ids:
                intent_path = str(INTENTS_DIR / f"{intent_id}.json")
                yield {"event": "test:queued", "data": json.dumps({"intentId": intent_id, "intentPath": intent_path})}

                try:
                    options = RunnerOptions(
                        browser="chromium",
                        headed=headed,
                        environment=env_param,
                    )
                    runner = TestRunner(options)

                    final_result = None
                    async for event in runner.run_intent_streaming(intent_path):
                        event_name = event["event"]
                        if event_name == "run:complete":
                            final_result = event["data"]
                            yield {
                                "event": "test:complete",
                                "data": json.dumps({"intentId": intent_id, "result": final_result}),
                            }
                        else:
                            yield {"event": event_name, "data": json.dumps(event["data"])}

                    if final_result:
                        result = RunResult.model_validate(final_result)
                        await write_json_report(result)
                except Exception as e:
                    log.error(f"Test error for {intent_id}: {e}", exc_info=True)
                    yield {"event": "test:error", "data": json.dumps({"intentId": intent_id, "error": str(e)})}

            yield {"event": "run:complete", "data": json.dumps({"runId": run_id, "totalIntents": len(intent_ids)})}
        except Exception as e:
            yield {"event": "run:error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(generate())
