from __future__ import annotations

from dataclasses import dataclass

import anthropic
from playwright.async_api import Locator, Page

from engine.config import ANTHROPIC_API_KEY
from engine.core.errors import AIResolverError
from engine.core.locator_parser import execute_locator, is_valid_locator_string, sanitize_ai_response
from engine.schema.intent import SelectorTarget
from engine.utils.dom_snapshot import extract_dom_snapshot
from engine.utils.logger import create_logger
from engine.utils.screenshot import capture_viewport_screenshot

log = create_logger("ai-resolver")

DEFAULT_MODEL = "claude-sonnet-4-20250514"
MAX_RETRIES = 1

SYSTEM_PROMPT = """You are an expert at finding UI elements in web applications.
Given a screenshot and/or DOM snapshot of a webpage, your task is to identify the element that matches the user's description.

IMPORTANT RULES:
1. Return ONLY a Playwright locator string, nothing else
2. Use semantic locators in order of preference:
   - getByTestId('value') - if data-testid is available
   - getByRole('role', { name: 'text' }) - for buttons, links, etc.
   - getByLabel('text') - for form inputs with labels
   - getByPlaceholder('text') - for inputs with placeholder
   - getByText('text') - for visible text content
   - locator('css-selector') - only as last resort
3. Do NOT include 'page.' prefix
4. Do NOT wrap in code blocks or add explanation
5. You may chain .first(), .last(), .nth(n), or .filter({ hasText: 'text' })

Examples of valid responses:
- getByTestId('submit-btn')
- getByRole('button', { name: 'Submit' })
- getByLabel('Email address')
- getByText('Add to Cart')
- locator('[data-testid="product-card"]').first()"""


@dataclass
class AIResolverResult:
    locator: Locator
    locator_string: str
    confidence: float
    used_vision: bool


def _build_user_prompt(target: SelectorTarget, step_intent: str, dom_snapshot: str | None = None) -> str:
    prompt = f'Find the element for this action: "{step_intent}"\n\n'
    if target.text:
        prompt += f'- Contains text: "{target.text}"\n'
    if target.role:
        prompt += f'- Has role: "{target.role}"\n'
    if target.test_id:
        prompt += f'- Has data-testid: "{target.test_id}"\n'
    if target.label:
        prompt += f'- Has label: "{target.label}"\n'
    if target.placeholder:
        prompt += f'- Has placeholder: "{target.placeholder}"\n'
    if target.position:
        prompt += f'- Approximate position: ({target.position.get("x", 0)}, {target.position.get("y", 0)})\n'
    if dom_snapshot:
        prompt += f"\nDOM Snapshot:\n{dom_snapshot}\n"
    prompt += "\nReturn ONLY the Playwright locator string:"
    return prompt


async def resolve_with_ai(
    page: Page,
    target: SelectorTarget,
    step_intent: str,
    model: str = DEFAULT_MODEL,
    max_retries: int = MAX_RETRIES,
) -> AIResolverResult:
    if not ANTHROPIC_API_KEY:
        raise AIResolverError("ANTHROPIC_API_KEY environment variable is not set")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    dom_snapshot = await extract_dom_snapshot(page, max_depth=4, max_length=8000)

    screenshot = None
    try:
        screenshot = await capture_viewport_screenshot(page)
    except Exception as e:
        log.warning(f"Failed to capture screenshot for AI resolver: {e}")

    user_prompt = _build_user_prompt(target, step_intent, dom_snapshot)
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            content: list[dict] = []
            if screenshot:
                content.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": screenshot["base64"]},
                })
            content.append({"type": "text", "text": user_prompt})

            response = client.messages.create(
                model=model,
                max_tokens=256,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": content}],
            )

            text_block = next((b for b in response.content if b.type == "text"), None)
            if not text_block:
                raise AIResolverError("No text response from Claude")

            raw = text_block.text
            locator_string = sanitize_ai_response(raw)

            if not is_valid_locator_string(locator_string):
                raise AIResolverError(f'Invalid locator string from AI: "{locator_string}"', raw)

            loc = execute_locator(page, locator_string)
            if not loc:
                raise AIResolverError(f'Failed to execute locator: "{locator_string}"', raw)

            await loc.wait_for(state="visible", timeout=5000)

            return AIResolverResult(
                locator=loc,
                locator_string=locator_string,
                confidence=0.75,
                used_vision=screenshot is not None,
            )

        except Exception as e:
            last_error = e
            log.warning(f"AI resolver attempt {attempt} failed: {e}")
            if attempt < max_retries:
                continue

    raise AIResolverError(
        f"AI resolver failed after {max_retries + 1} attempts: {last_error}",
        cause=last_error,
    )
