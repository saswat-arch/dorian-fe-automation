from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from engine.config import CACHE_DIR
from engine.utils.logger import create_logger

log = create_logger("cache-manager")

DEFAULT_MAX_AGE_DAYS = 7
DEFAULT_MIN_CONFIDENCE = 0.80


def _cache_path(intent_id: str, cache_dir: Path = CACHE_DIR) -> Path:
    return cache_dir / f"{intent_id}.cache.json"


def _is_expired(resolved_at: str, max_age_days: int) -> bool:
    try:
        resolved = datetime.fromisoformat(resolved_at.replace("Z", "+00:00"))
        diff = datetime.now(timezone.utc) - resolved
        return diff.days > max_age_days
    except Exception:
        return True


def load_cache(intent_id: str, cache_dir: Path = CACHE_DIR) -> dict:
    path = _cache_path(intent_id, cache_dir)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        log.warning(f"Failed to load cache: {path}")
        return {}


def save_cache(intent_id: str, cache: dict, cache_dir: Path = CACHE_DIR) -> None:
    path = _cache_path(intent_id, cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2))
    log.debug(f"Cache saved (intent={intent_id}, entries={len(cache)})")


def get_cached_selector(
    intent_id: str,
    step_id: str,
    max_age: int = DEFAULT_MAX_AGE_DAYS,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> dict | None:
    cache = load_cache(intent_id)
    entry = cache.get(step_id)
    if not entry:
        return None
    if entry.get("confidence", 0) < min_confidence:
        return None
    if _is_expired(entry.get("resolvedAt", ""), max_age):
        return None
    return entry


def set_cached_selector(
    intent_id: str,
    step_id: str,
    selector: str,
    strategy: str,
    confidence: float,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> None:
    if confidence < min_confidence and strategy == "ai-resolver":
        return

    cache = load_cache(intent_id)
    cache[step_id] = {
        "selector": selector,
        "strategy": strategy,
        "confidence": confidence,
        "resolvedAt": datetime.now(timezone.utc).isoformat(),
    }
    save_cache(intent_id, cache)


def invalidate_cached_selector(intent_id: str, step_id: str) -> None:
    cache = load_cache(intent_id)
    if step_id in cache:
        del cache[step_id]
        save_cache(intent_id, cache)
        log.debug(f"Cache entry invalidated (intent={intent_id}, step={step_id})")


def clear_cache(intent_id: str) -> None:
    path = _cache_path(intent_id)
    if path.exists():
        path.unlink()
        log.debug(f"Cache cleared (intent={intent_id})")


def clear_all_caches() -> int:
    if not CACHE_DIR.exists():
        return 0
    files = list(CACHE_DIR.glob("*.cache.json"))
    for f in files:
        f.unlink()
    log.info(f"All caches cleared ({len(files)} files)")
    return len(files)
