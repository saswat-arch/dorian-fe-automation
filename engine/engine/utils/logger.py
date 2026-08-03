from __future__ import annotations

from pathlib import Path

from loguru import logger

logger.remove()

_log_dir = Path(__file__).resolve().parent.parent.parent / "logs"
_log_dir.mkdir(parents=True, exist_ok=True)

logger.add(
    str(_log_dir / "engine.log"),
    rotation="10 MB",
    retention="7 days",
    level="DEBUG",
    format="{time:HH:mm:ss} | {level:<7} | {extra[module]:<20} | {message}",
    serialize=False,
)
logger.add(
    lambda msg: print(msg, end=""),
    level="INFO",
    format="<green>[{time:HH:mm:ss}]</green> <level>{level:<7}</level> | <cyan>{extra[module]:<20}</cyan> | {message}",
    colorize=True,
)


def create_logger(module: str) -> logger.__class__:
    return logger.bind(module=module)
