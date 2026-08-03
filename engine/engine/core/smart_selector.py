from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Optional

from playwright.async_api import Locator, Page

from engine.core.errors import SelectorNotFoundError
from engine.schema.intent import SelectorTarget
from engine.utils.logger import create_logger

log = create_logger("smart-selector")

DEFAULT_TIMEOUT = 5000
# Applied when a strategy matches more than one visible element and there's no
# positional data to disambiguate. Softer than the old 0.7 so semantically
# equivalent duplicates (e.g. two Close buttons in the same dialog, either of
# which dismisses it) still pass the confidence gate — the runner's post-click
# assertion check catches truly-wrong clicks.
MULTI_MATCH_PENALTY = 0.85

_ID_SELECTOR_RE = re.compile(r"^#[\w-]+$")
_ATTR_SELECTOR_RE = re.compile(r"^\[[^\]]+\]$")


def _score_css(selector: str) -> float:
    """
    Confidence a CSS selector deserves, based on its shape.

    An ID selector like `#concept-name` is inherently unique per page and
    should be trusted almost as much as a testId. A bare class or nested
    selector is fragile and stays at the old 0.60. Selectors that scope by
    content (:has-text) or by data-attributes are trusted more since they
    match on stable semantics, not layout classes.
    """
    s = selector.strip()
    if _ID_SELECTOR_RE.match(s):
        return 0.92
    if _ATTR_SELECTOR_RE.match(s):
        return 0.90
    has_scope = any(m in s for m in ("[role=", "[data-", "[type=", "[name=", "[aria-"))
    has_content_match = ":has-text(" in s or ":has(" in s
    # Compound scoped-content selector like `[role='dialog'] button:has-text('X')`
    # combines role/data-attribute scoping with content matching. This is more
    # precise than a bare role+name (which is global) and should be tried first.
    if has_scope and has_content_match:
        return 0.96
    if has_content_match:
        return 0.90
    if has_scope:
        return 0.85
    return 0.60


@dataclass
class SelectorResult:
    locator: Locator
    strategy: str
    confidence: float


def _distance(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def _build_strategies(page: Page, target: SelectorTarget) -> list[tuple[str, float, Locator | None]]:
    strategies = []

    if target.test_id:
        strategies.append(("testId", 0.99, page.get_by_test_id(target.test_id)))
    if target.role and target.text:
        strategies.append(("role+name", 0.95, page.get_by_role(target.role, name=target.text)))
    if target.label:
        strategies.append(("label-exact", 0.94, page.get_by_label(target.label, exact=True)))
    if target.label:
        strategies.append(("label", 0.93, page.get_by_label(target.label)))
    if target.placeholder:
        strategies.append(("placeholder", 0.90, page.get_by_placeholder(target.placeholder)))
    if target.role:
        strategies.append(("role", 0.85, page.get_by_role(target.role)))
    if target.text:
        strategies.append(("text", 0.80, page.get_by_text(target.text)))
    if target.css:
        strategies.append(("css", _score_css(target.css), page.locator(target.css)))
    if target.xpath:
        strategies.append(("xpath", 0.50, page.locator(f"xpath={target.xpath}")))

    # Try highest-confidence strategy first so a precise #id beats a bare `role`.
    strategies.sort(key=lambda s: s[1], reverse=True)
    return strategies


async def _is_editable(locator: Locator) -> bool:
    """True when the locator points to an editable field."""
    try:
        return await locator.is_editable(timeout=500)
    except Exception:
        return False


async def _pick_editable_candidate(locator: Locator, position: Optional[dict[str, float]] = None) -> Locator | None:
    """
    Choose an editable candidate from a possibly multi-match locator.

    If position data exists, pick the closest editable match; otherwise use the
    first editable candidate in DOM order.
    """
    count = await locator.count()
    if count == 0:
        return None

    best: Locator | None = None
    best_dist = float("inf")

    for i in range(count):
        candidate = locator.nth(i)
        try:
            await candidate.wait_for(state="visible", timeout=800)
        except Exception:
            continue

        if not await _is_editable(candidate):
            continue

        if not position:
            return candidate

        box = await candidate.bounding_box()
        if not box:
            if best is None:
                best = candidate
            continue
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2
        dist = _distance(position.get("x", 0), position.get("y", 0), cx, cy)
        if dist < best_dist:
            best_dist = dist
            best = candidate

    return best


async def _narrow_by_position(locator: Locator, position: dict[str, float]) -> Locator:
    count = await locator.count()
    if count <= 1:
        return locator.first

    closest_idx = 0
    closest_dist = float("inf")

    for i in range(count):
        el = locator.nth(i)
        box = await el.bounding_box()
        if box:
            cx = box["x"] + box["width"] / 2
            cy = box["y"] + box["height"] / 2
            dist = _distance(position.get("x", 0), position.get("y", 0), cx, cy)
            if dist < closest_dist:
                closest_dist = dist
                closest_idx = i

    return locator.nth(closest_idx)


async def resolve_selector(
    page: Page,
    target: SelectorTarget,
    action_type: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> SelectorResult:
    strategies = _build_strategies(page, target)
    attempted: list[str] = []

    for name, confidence, locator in strategies:
        if locator is None:
            continue
        attempted.append(name)
        try:
            await locator.first.wait_for(state="visible", timeout=timeout)
            count = await locator.count()

            final_locator = locator
            final_confidence = confidence

            if action_type == "type":
                editable = await _pick_editable_candidate(locator, target.position)
                if editable is None:
                    attempted.append(f"{name}:non-editable")
                    continue
                final_locator = editable
                if count > 1:
                    final_confidence *= MULTI_MATCH_PENALTY
            else:
                if count > 1:
                    final_confidence *= MULTI_MATCH_PENALTY
                    if target.position:
                        final_locator = await _narrow_by_position(locator, target.position)
                    else:
                        final_locator = locator.first

            return SelectorResult(locator=final_locator, strategy=name, confidence=final_confidence)
        except Exception:
            continue

    target_dict = target.model_dump(by_alias=True, exclude_none=True)
    raise SelectorNotFoundError(
        f"Could not find element matching target: {target_dict}",
        target_dict,
        attempted,
    )
