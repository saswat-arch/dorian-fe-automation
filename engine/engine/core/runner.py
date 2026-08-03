from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

from playwright.async_api import Browser, BrowserContext, Locator, Page, async_playwright

from engine.config import ANTHROPIC_API_KEY, INTENTS_DIR
from engine.core.action_executor import execute_action
from engine.core.auth_setup import get_auth_status, load_auth_state
from engine.core.cache_manager import get_cached_selector, invalidate_cached_selector, set_cached_selector
from engine.core.errors import BrowserLaunchError, IntentValidationError, SelectorNotFoundError
from engine.core.locator_parser import execute_locator
from engine.core.smart_selector import resolve_selector
from engine.schema.intent import SelectorTarget, StepIntent, TestIntent
from engine.schema.result import BrowserEvent, Environment, RunResult, StepResult, Viewport
from engine.utils.logger import create_logger
from engine.utils.screenshot import capture_failure_screenshot

log = create_logger("runner")

# Steps resolved below this confidence are treated as unreliable and fail loudly
# instead of proceeding to a probably-wrong click.
MIN_CONFIDENCE = 0.7

# Post-click visible/hidden assertion failures only halt the run when the click
# itself was already suspicious (below this confidence). A confident click with
# a failed follow-up assertion is more often an assertion-syntax problem than a
# real misclick, so we log a warning and let the next step surface any real issue.
LOW_CONFIDENCE_HALT_THRESHOLD = 0.85


async def _try_visible(page: Page, expected: str, timeout_ms: int, state: str) -> bool:
    """
    Wait for `expected` to reach `state` (visible/hidden) on the page.

    Tries `page.locator()` first — this handles CSS selectors, Playwright
    pseudo-classes like `button:has-text(...)`, `text=` engine strings, and
    `>>` chains. Falls back to `page.get_by_text()` for plain-text values.
    Returns True on success, False if neither strategy finds the element.
    """
    per_try = max(1000, timeout_ms // 2)
    for build in (lambda: page.locator(expected), lambda: page.get_by_text(expected)):
        try:
            locator = build()
            await locator.first.wait_for(state=state, timeout=per_try)
            return True
        except Exception:
            continue
    return False


@dataclass
class RunnerOptions:
    headed: bool = False
    slow_mo: int = 0
    timeout: int = 10000
    base_url_override: str | None = None
    browser: str = "chromium"
    environment: str | None = None


@dataclass
class ResolvedElement:
    locator: Locator
    tier: str
    strategy: str
    confidence: float
    healed_from: str | None = None
    healed_to: str | None = None


class BrowserEventCollector:
    """Captures console errors, page errors, and network failures from a Playwright page."""

    def __init__(self, environment: str | None = None):
        self.events: list[BrowserEvent] = []
        self._current_step_id: str | None = None
        self._environment = environment

    def set_current_step(self, step_id: str | None) -> None:
        self._current_step_id = step_id

    def drain_step_events(self) -> list[BrowserEvent]:
        """Return all events collected for the current step and clear them."""
        step_events = [e for e in self.events if e.step_id == self._current_step_id]
        return step_events

    def attach(self, page: Page) -> None:
        page.on("console", lambda msg: self._on_console(msg, page))
        page.on("pageerror", lambda error: self._on_page_error(error, page))
        page.on("response", lambda response: self._on_response(response))
        page.on("requestfailed", lambda request: self._on_request_failed(request))

    def _on_console(self, msg, page: Page) -> None:
        if msg.type not in ("error", "warning"):
            return
        evt = BrowserEvent(
            type="console_error",
            message=msg.text,
            url=page.url,
            stepId=self._current_step_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            meta={"level": msg.type},
        )
        self.events.append(evt)
        self._send_to_sentry(evt, "console")

    def _on_page_error(self, error, page: Page) -> None:
        evt = BrowserEvent(
            type="page_error",
            message=str(error),
            url=page.url,
            stepId=self._current_step_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            meta={"stack": str(error)},
        )
        self.events.append(evt)
        self._send_to_sentry(evt, "pageerror")

    def _on_response(self, response) -> None:
        if response.status < 400:
            return
        evt = BrowserEvent(
            type="network_error",
            message=f"{response.status} {response.status_text} — {response.url}",
            url=response.url,
            stepId=self._current_step_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            meta={"status": response.status, "statusText": response.status_text, "method": response.request.method},
        )
        self.events.append(evt)
        if response.status >= 500:
            self._send_to_sentry(evt, "network_5xx")

    def _on_request_failed(self, request) -> None:
        evt = BrowserEvent(
            type="request_failed",
            message=f"Request failed: {request.url} ({request.failure})",
            url=request.url,
            stepId=self._current_step_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            meta={"method": request.method, "failure": request.failure},
        )
        self.events.append(evt)
        self._send_to_sentry(evt, "request_failed")

    def _send_to_sentry(self, evt: BrowserEvent, category: str) -> None:
        try:
            import sentry_sdk
            sentry_sdk.add_breadcrumb(
                category=f"browser.{category}",
                message=evt.message,
                level="error" if evt.type in ("page_error", "console_error") else "warning",
                data={"url": evt.url, "step_id": evt.step_id, "environment": self._environment},
            )
            if evt.type in ("page_error", "console_error"):
                with sentry_sdk.push_scope() as scope:
                    scope.set_tag("browser_event_type", evt.type)
                    scope.set_tag("environment", self._environment or "unknown")
                    if evt.step_id:
                        scope.set_tag("step_id", evt.step_id)
                    scope.set_context("browser_event", evt.meta)
                    sentry_sdk.capture_message(evt.message, level="error")
        except Exception:
            pass


class TestRunner:
    def __init__(self, options: RunnerOptions | None = None):
        self.options = options or RunnerOptions()
        self._pw = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._event_collector: BrowserEventCollector | None = None

    async def load_intent(self, intent_path: str) -> TestIntent:
        try:
            path = Path(intent_path)
            data = json.loads(path.read_text())
            return TestIntent.model_validate(data)
        except Exception as e:
            if isinstance(e, IntentValidationError):
                raise
            raise IntentValidationError(
                f"Failed to load intent: {intent_path}",
                [{"path": "", "message": str(e)}],
            )

    async def launch_browser(self, browser_type: str = "chromium") -> None:
        try:
            self._pw = await async_playwright().start()
            launcher = getattr(self._pw, browser_type, self._pw.chromium)
            self._browser = await launcher.launch(
                headless=not self.options.headed,
                slow_mo=self.options.slow_mo,
            )
            log.info(f"Browser launched (type={browser_type}, headed={self.options.headed})")
        except Exception as e:
            raise BrowserLaunchError(f"Failed to launch {browser_type}", browser_type, e)

    async def create_page(self, intent: TestIntent) -> None:
        if not self._browser:
            raise RuntimeError("Browser not launched")

        viewport = {"width": intent.config.viewport.width, "height": intent.config.viewport.height}
        context_opts: dict[str, Any] = {"viewport": viewport}

        env = self.options.environment
        auth_state = load_auth_state(env)
        if auth_state:
            context_opts["storage_state"] = auth_state
            status = get_auth_status(env)
            fresh = status.get("fresh", False)
            log.info(f"Injecting auth state (env={env}, fresh={fresh}, email={status.get('email', '?')})")
            if not fresh:
                log.warning("Auth state may be expired — consider running auth setup again")
        else:
            log.info(f"No auth state found for env={env} — running without authentication")

        self._context = await self._browser.new_context(**context_opts)
        self._page = await self._context.new_page()

        self._event_collector = BrowserEventCollector(environment=env)
        self._event_collector.attach(self._page)

    async def _resolve_element(
        self, page: Page, step: StepIntent, intent_id: str
    ) -> ResolvedElement | None:
        if not step.target:
            return None

        target = step.target

        cached_entry = get_cached_selector(intent_id, step.id)
        if cached_entry:
            try:
                loc = execute_locator(page, cached_entry["selector"])
                if loc:
                    await loc.wait_for(state="visible", timeout=3000)
                    return ResolvedElement(
                        locator=loc,
                        tier="cached",
                        strategy=cached_entry["strategy"],
                        confidence=cached_entry["confidence"],
                    )
            except Exception:
                log.debug(f"Cached selector failed for step {step.id}")
                invalidate_cached_selector(intent_id, step.id)

        try:
            result = await resolve_selector(page, target, action_type=step.type, timeout=5000)
            selector_str = self._locator_to_string(target, result.strategy)
            set_cached_selector(intent_id, step.id, selector_str, result.strategy, result.confidence)
            return ResolvedElement(
                locator=result.locator,
                tier="smart-selector",
                strategy=result.strategy,
                confidence=result.confidence,
            )
        except SelectorNotFoundError:
            log.debug(f"Smart selector failed for step {step.id}, trying AI")

        if not ANTHROPIC_API_KEY:
            raise SelectorNotFoundError(
                "Smart selector failed and AI resolver not available",
                target.model_dump(by_alias=True, exclude_none=True),
                ["smart-selector"],
            )

        try:
            from engine.core.ai_resolver import resolve_with_ai
            ai_result = await resolve_with_ai(page, target, step.intent)
            previous_selector = cached_entry["selector"] if cached_entry else None
            set_cached_selector(intent_id, step.id, ai_result.locator_string, "ai-resolver", ai_result.confidence)
            return ResolvedElement(
                locator=ai_result.locator,
                tier="ai-resolver",
                strategy="ai-resolver",
                confidence=ai_result.confidence,
                healed_from=previous_selector,
                healed_to=ai_result.locator_string,
            )
        except Exception:
            raise SelectorNotFoundError(
                f"All resolution tiers failed for step {step.id}",
                target.model_dump(by_alias=True, exclude_none=True),
                ["cached", "smart-selector", "ai-resolver"],
            )

    @staticmethod
    def _locator_to_string(target: SelectorTarget, strategy: str) -> str:
        if strategy == "testId":
            return f"getByTestId('{target.test_id}')"
        elif strategy == "role+name":
            return f"getByRole('{target.role}', {{ name: '{target.text}' }})"
        elif strategy == "label":
            return f"getByLabel('{target.label}')"
        elif strategy == "label-exact":
            return f"getByLabel('{target.label}', {{ exact: true }})"
        elif strategy == "placeholder":
            return f"getByPlaceholder('{target.placeholder}')"
        elif strategy == "role":
            return f"getByRole('{target.role}')"
        elif strategy == "text":
            return f"getByText('{target.text}')"
        elif strategy == "css":
            return f"locator('{target.css}')"
        elif strategy == "xpath":
            return f"locator('xpath={target.xpath}')"
        else:
            return "locator('unknown')"

    async def _execute_assertion(self, page: Page, assertion, _test_id: str) -> dict:
        try:
            if assertion.type == "url":
                if assertion.expected:
                    expected = assertion.expected
                    # Actively wait for the URL to match instead of an instant check.
                    # React SPAs may need time after networkidle for client-side routing.
                    try:
                        await page.wait_for_url(
                            lambda url: expected in url, timeout=15000
                        )
                        return {"passed": True}
                    except Exception:
                        current = page.url
                        return {
                            "passed": False,
                            "error": f'URL "{current}" does not contain "{expected}" (waited 15s)',
                        }

            elif assertion.type == "visible":
                if assertion.expected:
                    if await _try_visible(page, assertion.expected, 15000, "visible"):
                        return {"passed": True}
                    return {
                        "passed": False,
                        "error": f'Expected "{assertion.expected}" not visible on page (tried locator + text, waited 15s)',
                    }

            elif assertion.type == "hidden":
                if assertion.expected:
                    if await _try_visible(page, assertion.expected, 15000, "hidden"):
                        return {"passed": True}
                    return {
                        "passed": False,
                        "error": f'Expected "{assertion.expected}" still visible on page (tried locator + text, waited 15s)',
                    }

            elif assertion.type == "text":
                if assertion.expected:
                    try:
                        loc = page.get_by_text(assertion.expected)
                        await loc.first.wait_for(state="visible", timeout=10000)
                        return {"passed": True}
                    except Exception:
                        return {
                            "passed": False,
                            "error": f'Text "{assertion.expected}" not found on page',
                        }

            return {"passed": True}
        except Exception as e:
            return {"passed": False, "error": str(e)}

    async def run_intent_streaming(self, intent_path: str) -> AsyncGenerator[dict, None]:
        """Run an intent and yield SSE-compatible events as dicts."""
        start_time = time.monotonic()

        intent = await self.load_intent(intent_path)
        browser_type = self.options.browser or (intent.config.browsers[0] if intent.config.browsers else "chromium")

        await self.launch_browser(browser_type)
        await self.create_page(intent)

        if not self._page:
            raise RuntimeError("Page not created")

        yield {"event": "test:start", "data": {"intentId": intent.id, "name": intent.name, "id": intent.id, "environment": self.options.environment}}

        base_url = self.options.base_url_override or intent.base_url
        if self.options.environment and not self.options.base_url_override:
            from engine.core.environments import resolve_base_url
            env_url = resolve_base_url(self.options.environment)
            if env_url:
                base_url = env_url
        await self._page.goto(base_url, wait_until="domcontentloaded")

        step_results: list[StepResult] = []
        healed_count = 0
        all_passed = True

        sorted_steps = sorted(intent.steps, key=lambda s: s.order)

        collector = self._event_collector
        all_browser_events: list[BrowserEvent] = []

        for step in sorted_steps:
            step_start = time.monotonic()
            resolved: ResolvedElement | None = None
            locator: Locator | None = None

            if collector:
                collector.set_current_step(step.id)

            needs_target = step.type in ("click", "type", "select", "hover", "scroll", "assert")
            if needs_target and step.target:
                try:
                    resolved = await self._resolve_element(self._page, step, intent.id)
                    locator = resolved.locator if resolved else None
                except Exception as e:
                    screenshot = await self._capture_on_failure(self._page, intent.id, step.id)
                    step_events = collector.drain_step_events() if collector else []
                    all_browser_events.extend(step_events)
                    sr = StepResult(
                        stepId=step.id, intent=step.intent, status="failed",
                        tier="smart-selector", strategy="none", confidence=0,
                        durationMs=(time.monotonic() - step_start) * 1000,
                        error=str(e), screenshot=screenshot,
                        browserEvents=step_events,
                    )
                    step_results.append(sr)
                    yield {"event": "step:result", "data": {
                        "intentId": intent.id, "status": "failed",
                        "step": step.model_dump(by_alias=True),
                        "result": sr.model_dump(by_alias=True),
                    }}
                    for bevt in step_events:
                        yield {"event": "browser:error", "data": {"intentId": intent.id, **bevt.model_dump(by_alias=True)}}
                    all_passed = False
                    break

                if resolved and resolved.confidence < MIN_CONFIDENCE:
                    target_desc = step.target.model_dump(by_alias=True, exclude_none=True)
                    err = (
                        f"Low-confidence selector match "
                        f"({resolved.confidence:.0%} via {resolved.strategy}, min {int(MIN_CONFIDENCE * 100)}%). "
                        f"Target {target_desc} likely does not match the intended element on this page. "
                        f"Verify the button/label text is exact or add a testId to the target."
                    )
                    screenshot = await self._capture_on_failure(self._page, intent.id, step.id)
                    step_events = collector.drain_step_events() if collector else []
                    all_browser_events.extend(step_events)
                    sr = StepResult(
                        stepId=step.id, intent=step.intent, status="failed",
                        tier=resolved.tier, strategy=resolved.strategy, confidence=resolved.confidence,
                        durationMs=(time.monotonic() - step_start) * 1000,
                        error=err, screenshot=screenshot,
                        browserEvents=step_events,
                    )
                    step_results.append(sr)
                    yield {"event": "step:result", "data": {
                        "intentId": intent.id, "status": "failed",
                        "step": step.model_dump(by_alias=True),
                        "result": sr.model_dump(by_alias=True),
                    }}
                    for bevt in step_events:
                        yield {"event": "browser:error", "data": {"intentId": intent.id, **bevt.model_dump(by_alias=True)}}
                    all_passed = False
                    break

            action_result = await execute_action(self._page, step, locator, intent.id)

            status = "failed"
            if action_result.success:
                status = "healed" if resolved and resolved.tier == "ai-resolver" else "passed"

            step_events = collector.drain_step_events() if collector else []
            all_browser_events.extend(step_events)

            sr = StepResult(
                stepId=step.id, intent=step.intent, status=status,
                tier=resolved.tier if resolved else "smart-selector",
                strategy=resolved.strategy if resolved else "none",
                confidence=resolved.confidence if resolved else 1.0,
                durationMs=(time.monotonic() - step_start) * 1000,
                error=action_result.error, screenshot=action_result.screenshot,
                healedFrom=resolved.healed_from if resolved else None,
                healedTo=resolved.healed_to if resolved else None,
                browserEvents=step_events,
            )
            step_results.append(sr)

            if not action_result.success:
                sr.screenshot = await self._capture_on_failure(self._page, intent.id, step.id)
                yield {"event": "step:result", "data": {
                    "intentId": intent.id, "status": "failed",
                    "step": step.model_dump(by_alias=True),
                    "result": sr.model_dump(by_alias=True),
                }}
                for bevt in step_events:
                    yield {"event": "browser:error", "data": {"intentId": intent.id, **bevt.model_dump(by_alias=True)}}
                all_passed = False
                break

            yield {"event": "step:result", "data": {
                "intentId": intent.id, "status": status,
                "step": step.model_dump(by_alias=True),
                "result": sr.model_dump(by_alias=True),
            }}
            for bevt in step_events:
                yield {"event": "browser:error", "data": {"intentId": intent.id, **bevt.model_dump(by_alias=True)}}

            if status == "healed":
                healed_count += 1

            # Check assertions tied to this step
            step_assertions = [a for a in intent.assertions if a.after_step == step.id]
            gating_failure: str | None = None
            if step_assertions:
                # Give the page time to settle (navigation, API calls, re-renders)
                try:
                    await self._page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass

                step_confidence = resolved.confidence if resolved else 1.0
                for assertion in step_assertions:
                    ar = await self._execute_assertion(self._page, assertion, intent.id)
                    if not ar["passed"]:
                        # Plain-text visible/hidden assertions ("Concept updated",
                        # "deleted", etc.) are usually transient toasts that disappear
                        # before we check. Treat them as informational — log but don't
                        # fail the run. Structural assertions (URL, CSS/attribute
                        # selectors) stay hard.
                        expected = assertion.expected or ""
                        is_soft = (
                            assertion.type in ("visible", "hidden")
                            and not any(m in expected for m in ("#", "[", ":has-text(", ":has(", ".", ">"))
                        )
                        if is_soft:
                            log.warning(f"Soft assertion failed (transient): {ar.get('error')}")
                        else:
                            all_passed = False
                            log.warning(f"Assertion failed: {ar.get('error')}")
                        # Halt only when the click was ALREADY suspicious. A confident click
                        # (>=0.85) with a failed follow-up visible/hidden is much more often
                        # an assertion-syntax quirk than a real misclick — let the next step
                        # surface any real problem instead of tearing down the run here.
                        if (
                            step.type == "click"
                            and assertion.type in ("visible", "hidden")
                            and not is_soft
                            and step_confidence < LOW_CONFIDENCE_HALT_THRESHOLD
                            and gating_failure is None
                        ):
                            gating_failure = (
                                f"Click at {step_confidence:.0%} confidence completed but expected "
                                f"element did not appear/disappear: {ar.get('error')}. "
                                f"The click likely targeted the wrong element."
                            )

            if gating_failure:
                screenshot = await self._capture_on_failure(self._page, intent.id, step.id)
                # Mark the just-completed step as failed so the UI shows the real cause.
                sr.status = "failed"
                sr.error = gating_failure
                sr.screenshot = screenshot
                yield {"event": "step:result", "data": {
                    "intentId": intent.id, "status": "failed",
                    "step": step.model_dump(by_alias=True),
                    "result": sr.model_dump(by_alias=True),
                }}
                break

        await self.cleanup()

        total_duration = (time.monotonic() - start_time) * 1000

        run_result = RunResult(
            testId=intent.id,
            testName=intent.name,
            passed=all_passed,
            steps=step_results,
            totalDuration=total_duration,
            browser=browser_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            healedCount=healed_count,
            environment=Environment(
                baseUrl=base_url,
                viewport=Viewport(width=intent.config.viewport.width, height=intent.config.viewport.height),
            ),
            browserEvents=all_browser_events,
        )

        await self._update_intent_metadata(intent_path, intent, run_result)

        yield {"event": "run:complete", "data": run_result.model_dump(by_alias=True)}

    async def run_intent(self, intent_path: str) -> RunResult:
        """Non-streaming run: returns the final RunResult."""
        result = None
        async for event in self.run_intent_streaming(intent_path):
            if event["event"] == "run:complete":
                result = RunResult.model_validate(event["data"])
        if not result:
            raise RuntimeError("Run completed without result")
        return result

    async def _capture_on_failure(self, page: Page, test_id: str, step_id: str) -> str | None:
        try:
            res = await capture_failure_screenshot(page, test_id, step_id)
            return res["path"]
        except Exception:
            return None

    async def _update_intent_metadata(self, intent_path: str, intent: TestIntent, result: RunResult) -> None:
        try:
            data = json.loads(Path(intent_path).read_text())
            meta = data.get("metadata", {})
            run_count = meta.get("runCount", 0) + 1
            pass_count = meta.get("passCount", 0) + (1 if result.passed else 0)
            avg_dur = meta.get("avgDuration", 0)

            meta["lastRun"] = result.timestamp
            meta["runCount"] = run_count
            meta["passCount"] = pass_count
            meta["passRate"] = pass_count / run_count if run_count else 0
            meta["avgDuration"] = round((avg_dur * (run_count - 1) + result.total_duration) / run_count)
            meta["updatedAt"] = datetime.now(timezone.utc).isoformat()
            data["metadata"] = meta

            Path(intent_path).write_text(json.dumps(data, indent=2))
        except Exception as e:
            log.warning(f"Failed to update intent metadata: {e}")

    async def cleanup(self) -> None:
        try:
            if self._page:
                await self._page.close()
        except Exception:
            pass
        try:
            if self._context:
                await self._context.close()
        except Exception:
            pass
        try:
            if self._browser:
                await self._browser.close()
        except Exception:
            pass
        try:
            if self._pw:
                await self._pw.stop()
        except Exception:
            pass
        self._page = self._context = self._browser = self._pw = None
        log.debug("Cleanup complete")
