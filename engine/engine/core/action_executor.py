from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional

from playwright.async_api import Locator, Page

from engine.schema.intent import StepIntent
from engine.utils.logger import create_logger
from engine.utils.screenshot import capture_failure_screenshot

log = create_logger("action-executor")

DEFAULT_SETTLE_DELAY = 0.2
DEFAULT_TIMEOUT = 10000


@dataclass
class ActionResult:
    success: bool
    duration_ms: float
    error: Optional[str] = None
    screenshot: Optional[str] = None
    extra: dict = field(default_factory=dict)


async def _settle(seconds: float) -> None:
    await asyncio.sleep(seconds)


async def execute_navigate(page: Page, step: StepIntent) -> ActionResult:
    t0 = time.monotonic()
    try:
        url = step.url or step.value
        if not url:
            return ActionResult(success=False, duration_ms=0, error="Navigate step requires a url or value (URL)")

        full_url = url if url.startswith("http") else f"{page.url.rstrip('/')}/{url.lstrip('/')}"
        await page.goto(full_url, timeout=DEFAULT_TIMEOUT, wait_until="domcontentloaded")
        await page.wait_for_load_state("domcontentloaded", timeout=DEFAULT_TIMEOUT)
        log.debug(f"Navigate complete: {full_url}")
        return ActionResult(success=True, duration_ms=_elapsed(t0))
    except Exception as e:
        return ActionResult(success=False, duration_ms=_elapsed(t0), error=str(e))


async def execute_click(page: Page, locator: Locator, step: StepIntent) -> ActionResult:
    t0 = time.monotonic()
    try:
        url_before = page.url

        # Ensure the element is scrolled into view and actionable
        await locator.scroll_into_view_if_needed(timeout=5000)
        await locator.click()
        log.debug(f"Click dispatched on: {step.intent}")

        # Give JavaScript time to initiate network requests before checking idle
        await asyncio.sleep(0.8)

        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        # If the URL hasn't changed, give React SPAs extra time for
        # state updates that trigger client-side navigation
        if page.url == url_before:
            await asyncio.sleep(1.0)

        if page.url != url_before:
            log.debug(f"Click caused navigation: {url_before} → {page.url}")

        return ActionResult(success=True, duration_ms=_elapsed(t0))
    except Exception as e:
        return ActionResult(success=False, duration_ms=_elapsed(t0), error=str(e))


async def execute_type(page: Page, locator: Locator, step: StepIntent) -> ActionResult:
    t0 = time.monotonic()
    try:
        if step.value is None:
            return ActionResult(success=False, duration_ms=0, error="Type step requires a value")
        await locator.click()
        await locator.fill("")
        await locator.fill(step.value)

        # Dispatch bubbling events so React's event delegation picks up the value.
        # Plain dispatch_event("change") defaults to bubbles=false which React ignores.
        try:
            await locator.evaluate(
                """el => {
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                    el.dispatchEvent(new FocusEvent('blur', { bubbles: true }));
                }"""
            )
        except Exception:
            pass

        # Verify the value actually stuck (React may have overwritten it)
        try:
            actual = await locator.input_value(timeout=2000)
            if actual != step.value:
                log.debug(f"fill() value mismatch, falling back to press_sequentially")
                await locator.click()
                await locator.fill("")
                await locator.press_sequentially(step.value, delay=30)
        except Exception:
            pass

        await _settle(DEFAULT_SETTLE_DELAY)
        return ActionResult(success=True, duration_ms=_elapsed(t0))
    except Exception as e:
        return ActionResult(success=False, duration_ms=_elapsed(t0), error=str(e))


async def execute_select(page: Page, locator: Locator, step: StepIntent) -> ActionResult:
    t0 = time.monotonic()
    try:
        if step.value is None:
            return ActionResult(success=False, duration_ms=0, error="Select step requires a value")
        await locator.select_option(step.value)
        await _settle(DEFAULT_SETTLE_DELAY)
        return ActionResult(success=True, duration_ms=_elapsed(t0))
    except Exception as e:
        return ActionResult(success=False, duration_ms=_elapsed(t0), error=str(e))


async def execute_hover(page: Page, locator: Locator, step: StepIntent) -> ActionResult:
    t0 = time.monotonic()
    try:
        await locator.hover()
        await _settle(DEFAULT_SETTLE_DELAY)
        return ActionResult(success=True, duration_ms=_elapsed(t0))
    except Exception as e:
        return ActionResult(success=False, duration_ms=_elapsed(t0), error=str(e))


async def execute_wait(page: Page, step: StepIntent) -> ActionResult:
    t0 = time.monotonic()
    try:
        ms = step.wait_ms or 1000
        await page.wait_for_timeout(ms)
        return ActionResult(success=True, duration_ms=_elapsed(t0))
    except Exception as e:
        return ActionResult(success=False, duration_ms=_elapsed(t0), error=str(e))


async def execute_scroll(page: Page, locator: Locator | None, step: StepIntent) -> ActionResult:
    t0 = time.monotonic()
    try:
        if locator:
            await locator.scroll_into_view_if_needed()
        else:
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
        await _settle(DEFAULT_SETTLE_DELAY)
        return ActionResult(success=True, duration_ms=_elapsed(t0))
    except Exception as e:
        return ActionResult(success=False, duration_ms=_elapsed(t0), error=str(e))


async def execute_assert(page: Page, locator: Locator | None, step: StepIntent) -> ActionResult:
    t0 = time.monotonic()
    try:
        if locator:
            await locator.wait_for(state="visible", timeout=5000)
        return ActionResult(success=True, duration_ms=_elapsed(t0))
    except Exception as e:
        return ActionResult(success=False, duration_ms=_elapsed(t0), error=str(e))


async def execute_screenshot(page: Page, step: StepIntent, test_id: str) -> ActionResult:
    t0 = time.monotonic()
    try:
        result = await capture_failure_screenshot(page, test_id, step.id)
        return ActionResult(success=True, duration_ms=_elapsed(t0), screenshot=result["path"])
    except Exception as e:
        return ActionResult(success=False, duration_ms=_elapsed(t0), error=str(e))


async def execute_action(
    page: Page,
    step: StepIntent,
    locator: Locator | None,
    test_id: str,
) -> ActionResult:
    log.debug(f"Executing {step.type}: {step.intent}")

    action = step.type
    if action == "navigate":
        return await execute_navigate(page, step)
    elif action == "click":
        if not locator:
            return ActionResult(success=False, duration_ms=0, error="Click requires a locator")
        return await execute_click(page, locator, step)
    elif action == "type":
        if not locator:
            return ActionResult(success=False, duration_ms=0, error="Type requires a locator")
        return await execute_type(page, locator, step)
    elif action == "select":
        if not locator:
            return ActionResult(success=False, duration_ms=0, error="Select requires a locator")
        return await execute_select(page, locator, step)
    elif action == "hover":
        if not locator:
            return ActionResult(success=False, duration_ms=0, error="Hover requires a locator")
        return await execute_hover(page, locator, step)
    elif action == "wait":
        return await execute_wait(page, step)
    elif action == "scroll":
        return await execute_scroll(page, locator, step)
    elif action == "assert":
        return await execute_assert(page, locator, step)
    elif action == "screenshot":
        return await execute_screenshot(page, step, test_id)
    else:
        return ActionResult(success=False, duration_ms=0, error=f"Unknown action type: {step.type}")


def _elapsed(t0: float) -> float:
    return (time.monotonic() - t0) * 1000
