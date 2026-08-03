from __future__ import annotations

import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path, override=True)

# Playwright needs these as actual env vars before it's imported.
# Bundled Node driver can hang on newer macOS — prefer system Node from PATH.
_pw_browsers = os.getenv("PLAYWRIGHT_BROWSERS_PATH")
if _pw_browsers:
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = _pw_browsers

_pw_node = os.getenv("PLAYWRIGHT_NODEJS_PATH") or shutil.which("node")
if _pw_node:
    os.environ["PLAYWRIGHT_NODEJS_PATH"] = _pw_node

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INTENTS_DIR = PROJECT_ROOT / "intents"
SUITES_DIR = PROJECT_ROOT / "suites"
REPORTS_DIR = PROJECT_ROOT / "reports"
KNOWLEDGEBASE_DIR = PROJECT_ROOT / "knowledgebase"
DB_PATH = KNOWLEDGEBASE_DIR / "app.db"
AUTH_DIR = PROJECT_ROOT / ".auth"
CACHE_DIR = INTENTS_DIR / ".cache"

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
JAM_ACCESS_TOKEN: str = os.getenv("JAM_ACCESS_TOKEN", "")
AUTH_EMAIL: str = os.getenv("AUTH_EMAIL", "")

# Auth method: "interactive" (default) — open browser, log in manually, state is cached
AUTH_METHOD: str = os.getenv("AUTH_METHOD", "interactive")
