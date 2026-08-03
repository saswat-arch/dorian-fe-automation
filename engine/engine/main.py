from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

_sentry_dsn = os.getenv("SENTRY_DSN", "")
if _sentry_dsn:
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=_sentry_dsn,
            environment=os.getenv("SENTRY_ENV", "development"),
            traces_sample_rate=0.5,
            send_default_pii=False,
        )
    except ImportError:
        pass

from engine.routes.auth_state_routes import router as auth_state_router
from engine.routes.environments import router as envs_router
from engine.routes.intents import router as intents_router
from engine.routes.jam_import import router as jam_router
from engine.routes.knowledgebase_routes import router as kb_router
from engine.routes.reports import router as reports_router
from engine.routes.run import router as run_router
from engine.routes.stats import router as stats_router
from engine.routes.suites import ensure_preset_suites, router as suites_router

app = FastAPI(title="QA Autopilot Engine", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(intents_router)
app.include_router(run_router)
app.include_router(reports_router)
app.include_router(kb_router)
app.include_router(stats_router)
app.include_router(auth_state_router)
app.include_router(envs_router)
app.include_router(jam_router)
app.include_router(suites_router)

ensure_preset_suites()


@app.get("/health")
async def health():
    return {"status": "ok", "engine": "python"}


def run():
    uvicorn.run("engine.main:app", host="0.0.0.0", port=8000, reload=True, loop="asyncio")


if __name__ == "__main__":
    run()
