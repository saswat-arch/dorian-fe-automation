from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from engine.config import REPORTS_DIR
from engine.schema.result import RunResult
from engine.utils.logger import create_logger

log = create_logger("json-reporter")


async def write_json_report(result: RunResult, output_dir: Path | None = None) -> str:
    out = output_dir or REPORTS_DIR
    out.mkdir(parents=True, exist_ok=True)

    filename = f"{result.test_id}-{int(time.time() * 1000)}.json"
    filepath = out / filename

    report = {
        "version": "1.0.0",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "result": result.model_dump(by_alias=True),
        "metadata": {
            "runner": "qa-autopilot",
            "pythonVersion": sys.version.split()[0],
        },
    }

    filepath.write_text(json.dumps(report, indent=2))
    log.info(f"JSON report written: {filepath}")
    return str(filepath)
