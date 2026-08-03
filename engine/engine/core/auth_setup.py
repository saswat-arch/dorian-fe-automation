from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from engine.config import AUTH_DIR, AUTH_EMAIL
from engine.utils.logger import create_logger

log = create_logger("auth-setup")

DEFAULT_STATE_FILE = "default.json"
AUTH_META_FILE = "meta.json"

DEFAULT_AUTH_CONFIG = {
    "baseUrl": "https://staging-prism.upcover.com/",
    "method": "interactive",
    "steps": {},
    "waitAfterAuth": 5000,
    "maxAgeHours": 24,
}

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _env_dir(environment: str | None) -> Path:
    if environment:
        return AUTH_DIR / environment
    return AUTH_DIR


def _config_path() -> Path:
    return AUTH_DIR / "config.json"


def _state_path(environment: str | None = None) -> Path:
    return _env_dir(environment) / DEFAULT_STATE_FILE


def _meta_path(environment: str | None = None) -> Path:
    return _env_dir(environment) / AUTH_META_FILE


# ---------------------------------------------------------------------------
# Config + status (unchanged — used by tests and runner)
# ---------------------------------------------------------------------------


def load_auth_config() -> dict:
    path = _config_path()
    if path.exists():
        return json.loads(path.read_text())
    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(DEFAULT_AUTH_CONFIG, indent=2))
    log.info(f"Default auth config created at {path}")
    return DEFAULT_AUTH_CONFIG


def save_auth_config(config: dict) -> None:
    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    _config_path().write_text(json.dumps(config, indent=2))


def get_auth_status(environment: str | None = None) -> dict:
    """Check if auth state exists and is fresh for a given environment."""
    state_path = _state_path(environment)
    meta_path = _meta_path(environment)

    if not state_path.exists():
        return {"authenticated": False, "reason": "no_state", "environment": environment}

    if not meta_path.exists():
        return {"authenticated": True, "fresh": False, "reason": "no_meta", "environment": environment}

    meta = json.loads(meta_path.read_text())
    created_at = meta.get("createdAt", "")
    email = meta.get("email", "")
    max_age_hours = meta.get("maxAgeHours", 24)

    try:
        created = datetime.fromisoformat(created_at)
        age_hours = (datetime.now(timezone.utc) - created).total_seconds() / 3600
        fresh = age_hours < max_age_hours
        return {
            "authenticated": True,
            "fresh": fresh,
            "email": email,
            "createdAt": created_at,
            "ageHours": round(age_hours, 1),
            "maxAgeHours": max_age_hours,
            "environment": environment,
        }
    except (ValueError, TypeError):
        return {"authenticated": True, "fresh": False, "reason": "invalid_meta", "environment": environment}


def load_auth_state(environment: str | None = None) -> Optional[dict]:
    """Load auth state for a given environment (or the legacy global state)."""
    state_path = _state_path(environment)
    if not state_path.exists():
        if environment:
            legacy = _state_path(None)
            if legacy.exists():
                log.info(f"No auth state for env '{environment}', falling back to legacy global state")
                try:
                    return json.loads(legacy.read_text())
                except (json.JSONDecodeError, TypeError):
                    return None
        return None
    try:
        return json.loads(state_path.read_text())
    except (json.JSONDecodeError, TypeError):
        return None


load_global_auth_state = load_auth_state


async def clear_auth_state(environment: str | None = None) -> None:
    """Remove saved auth state for a specific environment (or legacy global)."""
    for path in [_state_path(environment), _meta_path(environment)]:
        if path.exists():
            path.unlink()
    log.info(f"Auth state cleared (env={environment})")


# ---------------------------------------------------------------------------
# Interactive auth — runs Playwright in a standalone process (CLI)
# ---------------------------------------------------------------------------


def _is_logged_in(page) -> bool:
    """Detect Auth0 session via cookies or localStorage (more reliable than URL alone)."""
    try:
        return page.evaluate(
            """() => {
                if (document.cookie.includes('is.authenticated=true')) return true;
                for (const k of Object.keys(localStorage)) {
                    if (k.includes('auth0spajs') && k.includes('openid')) return true;
                }
                return false;
            }"""
        )
    except Exception:
        return False


def run_auth_setup_sync(
    environment: str | None = None,
    base_url_override: str | None = None,
    config_override: Optional[dict] = None,
) -> dict:
    """
    Open a browser, let the user complete login manually, then save state.
    Must be run outside uvicorn (via CLI or spawned subprocess).
    """
    from playwright.sync_api import sync_playwright

    config = config_override or load_auth_config()
    base_url = base_url_override or config.get("baseUrl", "https://staging-prism.upcover.com/")

    if environment and not base_url_override:
        from engine.core.environments import resolve_base_url
        env_url = resolve_base_url(environment)
        if env_url:
            base_url = env_url

    wait_after = config.get("waitAfterAuth", 5000)
    email = AUTH_EMAIL

    log.info(f"Auth setup: base_url={base_url}, env={environment}")
    print("\n" + "=" * 60)
    print("  AUTH SETUP — complete login in the browser window")
    print("  Enter your email, OTP, etc. The engine saves state when done.")
    print("=" * 60 + "\n")

    pw = sync_playwright().start()
    try:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        page = context.new_page()

        page.goto(base_url, wait_until="domcontentloaded", timeout=30000)

        deadline = datetime.now().timestamp() + 180
        while datetime.now().timestamp() < deadline:
            page.wait_for_timeout(1000)
            if _is_logged_in(page):
                log.info("Login detected (auth cookie/localStorage present)")
                break
        else:
            raise TimeoutError("Login timed out after 180s. Complete login in the browser and try again.")

        page.wait_for_timeout(wait_after)

        final_url = page.url
        env_dir = _env_dir(environment)
        env_dir.mkdir(parents=True, exist_ok=True)

        storage_state = context.storage_state()
        _state_path(environment).write_text(json.dumps(storage_state, indent=2))

        meta = {
            "email": email,
            "baseUrl": base_url,
            "method": "interactive",
            "finalUrl": final_url,
            "environment": environment,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "maxAgeHours": config.get("maxAgeHours", 24),
        }
        _meta_path(environment).write_text(json.dumps(meta, indent=2))

        log.info(f"Auth state saved to {_state_path(environment)}")
        print(f"\nAuth saved for env={environment}. Final URL: {final_url}\n")
        os._exit(0)
    except Exception as e:
        log.error(f"Auth setup failed: {e}", exc_info=True)
        raise


def _engine_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def spawn_auth_setup(environment: str | None = None) -> dict:
    """Launch auth setup as a detached subprocess (safe from uvicorn)."""
    engine_root = _engine_root()
    cmd = [
        sys.executable,
        "-m",
        "engine.core.auth_setup",
        "--env",
        environment or "staging",
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(engine_root)
    env["PYTHONUNBUFFERED"] = "1"

    log_file = engine_root.parent / ".auth" / "setup.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a") as log_f:
        log_f.write(f"\n--- auth setup env={environment} ---\n")
        subprocess.Popen(
            cmd,
            cwd=str(engine_root),
            env=env,
            start_new_session=True,
            stdout=log_f,
            stderr=subprocess.STDOUT,
        )
    log.info(f"Auth setup subprocess started (env={environment}), log={log_file}")
    return {
        "started": True,
        "message": "Browser opening — complete login in the window that appears.",
        "environment": environment,
        "logPath": str(log_file),
    }


async def run_auth_setup(
    config_override: Optional[dict] = None,
    headed: bool = True,
    environment: str | None = None,
    base_url_override: str | None = None,
) -> dict:
    """API entry point — spawns CLI subprocess, returns immediately."""
    return spawn_auth_setup(environment)


# ---------------------------------------------------------------------------
# CLI: python -m engine.core.auth_setup --env staging
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive auth setup — saves browser state to .auth/")
    parser.add_argument("--env", default="staging", help="Environment name (default: staging)")
    args = parser.parse_args()
    run_auth_setup_sync(environment=args.env)


if __name__ == "__main__":
    main()
