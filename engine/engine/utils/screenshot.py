from __future__ import annotations

import base64
import time
from pathlib import Path

from playwright.async_api import Page

from engine.config import REPORTS_DIR

DEFAULT_SCREENSHOT_DIR = REPORTS_DIR / "screenshots"


async def capture_screenshot(
    page: Page,
    *,
    full_page: bool = True,
    quality: int = 80,
    img_type: str = "png",
    path: str | None = None,
) -> dict[str, str]:
    screenshot_path = Path(path) if path else DEFAULT_SCREENSHOT_DIR / f"screenshot-{int(time.time() * 1000)}.png"
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)

    opts: dict = {"path": str(screenshot_path), "full_page": full_page, "type": img_type}
    if img_type == "jpeg":
        opts["quality"] = quality

    buf = await page.screenshot(**opts)
    b64 = base64.b64encode(buf).decode()
    return {"path": str(screenshot_path), "base64": b64}


async def capture_viewport_screenshot(page: Page, quality: int = 80) -> dict[str, str]:
    return await capture_screenshot(page, full_page=False, quality=quality, img_type="jpeg")


async def capture_failure_screenshot(page: Page, test_id: str, step_id: str) -> dict[str, str]:
    path = str(REPORTS_DIR / f"{test_id}-{step_id}-{int(time.time() * 1000)}.png")
    return await capture_screenshot(page, full_page=True, path=path)


def base64_to_data_uri(b64: str, mime: str = "image/png") -> str:
    return f"data:{mime};base64,{b64}"
