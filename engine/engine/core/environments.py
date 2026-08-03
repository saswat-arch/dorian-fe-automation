from __future__ import annotations

import json
import os
from pathlib import Path

from engine.config import AUTH_DIR
from engine.utils.logger import create_logger

log = create_logger("environments")

DEFAULT_ENVIRONMENTS: dict[str, dict] = {
    "dev": {
        "name": "Development",
        "baseUrl": os.getenv("ENV_DEV_URL", "https://dev-prism.upcover.com/"),
    },
    "staging": {
        "name": "Staging",
        "baseUrl": os.getenv("ENV_STAGING_URL", "https://staging-prism.upcover.com/"),
    },
    "prod": {
        "name": "Production",
        "baseUrl": os.getenv("ENV_PROD_URL", "https://prism.upcover.com/"),
    },
}

_ENVS_FILE = "environments.json"


def _envs_path() -> Path:
    return AUTH_DIR / _ENVS_FILE


def load_environments() -> dict[str, dict]:
    path = _envs_path()
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, TypeError):
            log.warning("Corrupt environments.json — using defaults")
    return _save_and_return_defaults()


def _save_and_return_defaults() -> dict[str, dict]:
    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    _envs_path().write_text(json.dumps(DEFAULT_ENVIRONMENTS, indent=2))
    return DEFAULT_ENVIRONMENTS


def save_environments(envs: dict[str, dict]) -> None:
    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    _envs_path().write_text(json.dumps(envs, indent=2))


def get_environment(env_key: str) -> dict | None:
    envs = load_environments()
    return envs.get(env_key)


def upsert_environment(key: str, name: str, base_url: str) -> dict[str, dict]:
    envs = load_environments()
    envs[key] = {"name": name, "baseUrl": base_url}
    save_environments(envs)
    return envs


def delete_environment(key: str) -> dict[str, dict]:
    envs = load_environments()
    envs.pop(key, None)
    save_environments(envs)
    return envs


def resolve_base_url(env_key: str) -> str | None:
    env = get_environment(env_key)
    return env["baseUrl"] if env else None
