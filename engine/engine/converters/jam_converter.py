from __future__ import annotations

import asyncio
import json
import random
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import anthropic
import httpx

from engine.config import ANTHROPIC_API_KEY, JAM_ACCESS_TOKEN, INTENTS_DIR
from engine.schema.intent import TestIntent
from engine.utils.logger import create_logger

log = create_logger("jam-converter")

JAM_MCP_URL = "https://mcp.jam.dev/mcp"


class JamAuthError(RuntimeError):
    """Raised when the Jam MCP endpoint rejects our access token (401/403)."""


class JamFetchError(RuntimeError):
    """Raised when every Jam MCP tool call fails, so we have no data to convert."""


CONVERTER_MODEL = "claude-sonnet-4-6"
CONVERTER_MAX_TOKENS = 8192
CONVERTER_MAX_RETRIES = 3
CONVERTER_REPAIR_PASSES = 2

# Hosts that are never the app under test — used both for base-URL detection
# and to filter noise in extracted URLs.
NON_APP_HOSTS = {
    "cdn.auth0.com",
    "auth0.com",
    "gstatic.com",
    "google.com",
    "googleapis.com",
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "unpkg.com",
    "jsdelivr.net",
    "cdnjs.cloudflare.com",
    "cloudflare.com",
    "sentry.io",
    "ingest.sentry.io",
    "mailosaur.com",
    "jam.dev",
}

SYSTEM_PROMPT = """You are an expert at converting Jam session recordings into structured test intent files.

INPUT PRIORITY:
The "Jam AI Analysis" section is your PRIMARY source. Each entry is a distinct user intent with:
- `summary`, `detail`, `userGoal`: what the user was doing
- `pageUrl`, `pageTitle`: where they were
- `evidence[]`: HTML snippets and narrative — use HTML fragments here to extract id/testId/label
- `keyActions[]`: each has `target` (HUMAN LABEL — trust this) and `selector` (Jam's suggestion — DO NOT trust, see below)
- `visualChanges[]` / `visualOutcome`: what the video showed after the action — generate visible/hidden assertions from these

CRITICAL — IGNORE Jam's `selector` field:
Jam's `keyActions[].selector` values are almost always **tailwind class salads** like:
  - `span.inline-flex.items-center`
  - `a.group.rounded-lg.border.bg-card.p-6.shadow-sm.transition-colors.hover:bg-accent`
  - `button.h-8.rounded-md.gap-1.5.px-3.cursor-pointer.bg-primary.text-primary-foreground`
These selectors match HUNDREDS of unrelated elements. DO NOT copy them into `target.css`. They are strictly worse than useless. Ignore them completely.

Instead, build selectors from:
1. HTML snippets in `evidence[]` — look for id, data-testid, data-*, role, type, name, placeholder attributes
2. The `keyActions[].target` HUMAN LABEL — this often contains row context like "View button for 'Automated Concept'" — use it for scoped selectors (see ROW SCOPING below)
3. The `pageUrl` context to identify modal/dialog scope

ROW SCOPING (critical for table/list action buttons):
When `keyActions[].target` describes a per-row action ("View button for 'X'", "Delete button for 'Y'", "Edit button for 'Z'"), do NOT generate a bare `role+text` selector — every row has that same button, so it'll match multiple. Instead scope by the row's unique text:

  Jam target: "View button for 'Automated Concept'"
  BAD:  { "role": "button", "text": "View" }
        → matches View on every row (multi-match penalty)
  GOOD: { "role": "button", "text": "View",
          "css": "tr:has-text('Automated Concept') button:has-text('View')" }

Same for cards: "Form Management card" → `[data-slot='card']:has-text('Form Management')` or `a:has-text('Form Management')` scoped to the section.

Prefer analysis data over raw events when they conflict. Only use raw events for interactions the analysis missed.

Authentication is handled separately by the engine. SKIP:
- Login button clicks, email/password entry, OTP entry
- Auth0 / Google / SSO redirects
- Gmail or email-provider interactions
The test runs in an already-authenticated browser session. Start from the FIRST meaningful post-login interaction. If the recording is *only* a login flow, produce steps for the final authenticated page.

Element targeting — the analysis's `evidence[]` field contains HTML snippets. For EACH element, populate AS MANY target fields as possible so the runner has multiple fallback strategies if any single identifier changes. Do not stop after one.

Extract from the HTML snippet:
- data-testid / data-test-id attribute → testId
- id attribute → css (as "#the-id")
- role attribute or implicit role (button, textbox, link, heading) + visible text → role + text
- placeholder attribute → placeholder
- <label> element pointing at this input, or aria-label → label

For inputs: an HTML snippet like `<input id="concept-name" placeholder="Concept name" aria-label="Concept name">` should produce a target with ALL of: css="#concept-name", placeholder="Concept name", label="Concept name". Not just one.

For buttons: `<button data-slot="button">+ New Concept</button>` should produce role="button" AND text="New Concept". If there's also a data-testid, populate testId too.

NEVER emit a target where every field is null. If the HTML has nothing usable, use role + text inferred from surrounding context.

CRITICAL — VERBATIM TEXT RULE (most common failure mode):
When you populate target.text, it MUST be an EXACT verbatim substring of the element's visible text as it appears in the HTML snippet. Copy the characters literally, preserving case and spacing.

DO NOT infer button labels from:
- URL path segments (e.g. `/concepts/create` does NOT imply the button says "Create concept")
- The user's own intent description (a description saying "create a concept" does NOT mean the button is labeled "Create concept")
- Jam's narrative summary of the click
- What the button "logically should be called"
- Adjacent breadcrumbs, page titles, or headings

If the HTML shows `<button>+ New Concept</button>`, target.text is "New Concept" (strip icons like "+", trim whitespace, but do not rename).
If the HTML shows `<button>Create</button>`, target.text is "Create" — even if the intent says "create a concept".

WRONG:
  URL: /admin/form-management/concepts
  HTML: <button data-slot="button">+ New Concept</button>
  → target: { "role": "button", "text": "Create concept" }   ← inferred from URL/intent, WRONG

RIGHT:
  URL: /admin/form-management/concepts
  HTML: <button data-slot="button">+ New Concept</button>
  → target: { "role": "button", "text": "New Concept" }      ← verbatim from HTML

If the HTML snippet is missing or truncated for a click event, prefer role-only targeting or leave text null. Do not make up text.

SCOPED SELECTOR RULE (prevents ambiguous multi-match failures):
When a click happens INSIDE a modal, dialog, drawer, popover, or dropdown, generic labels like "Close", "Save", "Cancel", "Delete" almost always appear multiple times elsewhere on the page. A bare `role="button", text="Close"` will match every Close button in the DOM and fail confidence checks. Detect modal context from the analysis's `pageUrl`, `evidence`, or the preceding step (which usually opened the modal), and scope the css selector accordingly:

  BAD:  { "role": "button", "text": "Close" }
        → matches modal Close, header Close, notification dismiss, etc.

  GOOD: { "role": "button", "text": "Close",
          "css": "[role='dialog'] button:has-text('Close')" }
        → scoped to the open dialog

Common scoping patterns:
- Inside a shadcn/Radix dialog: `[role='dialog'] button:has-text('X')` or `[data-state='open'] button:has-text('X')`
- Inside a popover: `[role='menu'] button:has-text('X')` or `[data-radix-popper-content-wrapper] button:has-text('X')`
- Inside a specific card: use the card's data-testid or aria-label as the scope

Apply this rule to ALL of: Close, Cancel, Save, Save changes, Delete, Confirm, OK, Yes, No — whenever the click is inside a modal/popover/drawer context.

Rules:
1. One user action = one step, except: group rapid sequential clicks on the SAME element.
2. For "type" steps, do NOT emit a preceding "click" step on the same input — the runner focuses inputs automatically before typing.
3. Extract every non-auth interaction — clicks, form fills, navigations.
4. Assertions: infer from navigation events and the analysis's `visualChanges` / `visualOutcome` fields. Include assertions at key checkpoints, not only at the end.
5. URL assertions: use RELATIVE paths against the base URL (e.g. "/all-risk-profiles"). Strip query strings and UUIDs — pick only the stable path segment.
6. Never include database IDs, UUIDs, or session tokens in assertions.
7. Never emit contradictory assertions after the same step (e.g. url == "/a" AND url == "/b"). Pick the FINAL settled URL.
8. For form submissions, assert the final destination URL, not intermediate redirects.
9. For click steps that open a modal/dialog, emit a `visible` assertion right after that step targeting the first form field in the dialog (by its id/testId). This lets the runner detect misclicks early.
10. For click steps that CLOSE a modal, emit a `hidden` assertion right after, scoped to the modal container (e.g. expected: `[role='dialog']`). This confirms the dismiss actually happened.

Emit results by calling the `emit_test_intent` tool. Do not respond with prose."""

INTENT_TOOL_SCHEMA: dict[str, Any] = {
    "name": "emit_test_intent",
    "description": "Emit the parsed test intent derived from the Jam recording.",
    "input_schema": {
        "type": "object",
        "required": ["name", "description", "steps", "assertions", "tags"],
        "properties": {
            "name": {"type": "string", "description": "Short descriptive test name."},
            "description": {"type": "string", "description": "One-sentence summary of what this test verifies."},
            "tags": {"type": "array", "items": {"type": "string"}, "description": "Category tags."},
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["id", "order", "type", "intent"],
                    "properties": {
                        "id": {"type": "string", "description": "step-N identifier."},
                        "order": {"type": "integer", "minimum": 1},
                        "type": {"type": "string", "enum": ["navigate", "click", "type", "select", "scroll", "hover", "wait"]},
                        "intent": {"type": "string", "description": "Human-readable action description."},
                        "target": {
                            "type": ["object", "null"],
                            "description": "Selector target. Include at least one of: testId, css, role+text, placeholder, label.",
                            "properties": {
                                "testId": {"type": ["string", "null"]},
                                "css": {"type": ["string", "null"]},
                                "role": {"type": ["string", "null"]},
                                "text": {"type": ["string", "null"]},
                                "placeholder": {"type": ["string", "null"]},
                                "label": {"type": ["string", "null"]},
                                "xpath": {"type": ["string", "null"]},
                            },
                        },
                        "value": {"type": ["string", "null"], "description": "Value for type/select actions."},
                        "url": {"type": ["string", "null"], "description": "Relative URL for navigate actions."},
                    },
                },
            },
            "assertions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["id", "afterStep", "type", "expected"],
                    "properties": {
                        "id": {"type": "string"},
                        "afterStep": {"type": "string", "description": "The step id this assertion follows."},
                        "intent": {"type": "string"},
                        "type": {"type": "string", "enum": ["url", "visible", "hidden", "text", "count", "enabled", "checked"]},
                        "expected": {"type": "string"},
                    },
                },
            },
        },
    },
}

USER_TEMPLATE = """Base URL: {baseUrl}

Recording Details:
{details}

Jam AI Analysis (PRIMARY SOURCE — Jam's own pre-computed intent extraction with video context. Each entry has HTML evidence, page URLs, visual outcomes, and Jam's suggested selectors. Trust this over raw events when they disagree):
{analysis}

Raw User Events (secondary — use only for interactions the analysis missed):
{events}

Console Logs:
{consoleLogs}

Network Requests (summarized):
{networkRequests}"""


def _parse_sse_response(text: str) -> Optional[dict]:
    """Parse SSE event stream to extract the JSON-RPC result."""
    result = None
    for line in text.strip().split("\n"):
        if line.startswith("data: "):
            try:
                result = json.loads(line[6:])
            except (json.JSONDecodeError, TypeError):
                pass
    return result


def _extract_text_from_mcp_result(data: Optional[dict]) -> str:
    """Extract text content from an MCP tool call result."""
    if not data or "result" not in data:
        return ""
    content = data["result"].get("content", [])
    all_text = ""
    for item in content:
        if item.get("type") == "text" and "text" in item:
            all_text += item["text"]
    return all_text


class JamMCPClient:
    """Handles MCP session lifecycle with the Jam API."""

    def __init__(self, token: str):
        self.token = token
        self.session_id: Optional[str] = None
        self._msg_id = 0

    def _next_id(self) -> int:
        self._msg_id += 1
        return self._msg_id

    async def _ensure_session(self, client: httpx.AsyncClient) -> None:
        if self.session_id:
            return

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {self.token}",
        }

        init_resp = await client.post(
            JAM_MCP_URL,
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "qa-autopilot", "version": "1.0.0"},
                },
            },
        )
        init_resp.raise_for_status()
        self.session_id = init_resp.headers.get("mcp-session-id")

        if not self.session_id:
            raise RuntimeError("Jam MCP did not return a session ID")

        log.info(f"Jam MCP session established: {self.session_id[:16]}...")

        await client.post(
            JAM_MCP_URL,
            headers={**headers, "Mcp-Session-Id": self.session_id},
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        )

    async def call_tool(self, client: httpx.AsyncClient, tool_name: str, args: dict) -> Any:
        await self._ensure_session(client)

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {self.token}",
            "Mcp-Session-Id": self.session_id,
        }

        log.info(f"Calling Jam MCP: {tool_name}")

        resp = await client.post(
            JAM_MCP_URL,
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": args},
            },
        )
        if resp.status_code in (401, 403):
            raise JamAuthError(
                f"Jam MCP rejected the access token ({resp.status_code}). "
                "Check JAM_ACCESS_TOKEN in .env — it may be expired or invalid."
            )
        resp.raise_for_status()

        data = _parse_sse_response(resp.text)
        if not data:
            log.warning(f"Jam MCP {tool_name}: could not parse SSE response")
            return None

        if "error" in data:
            log.error(f"Jam MCP {tool_name} error: {data['error']}")
            raise RuntimeError(f"Jam MCP {tool_name}: {data['error']}")

        text = _extract_text_from_mcp_result(data)
        if text:
            log.info(f"Jam MCP {tool_name}: {len(text)} chars")
            try:
                return json.loads(text)
            except (json.JSONDecodeError, TypeError):
                return text

        return data.get("result", {})


def extract_jam_id(input_str: str) -> Optional[str]:
    """Extract a Jam URL (with UUID including hyphens) from input."""
    match = re.search(r"https://jam\.dev/c/[a-zA-Z0-9-]+", input_str)
    return match.group(0) if match else None


def _summarize_network_requests(network_data: Any, max_entries: int = 50) -> str:
    """Summarize network requests to avoid exceeding token limits."""
    if not network_data:
        return "[]"

    if isinstance(network_data, str):
        try:
            network_data = json.loads(network_data)
        except (json.JSONDecodeError, TypeError):
            return network_data[:5000]

    if not isinstance(network_data, list):
        return json.dumps(network_data, indent=2)[:5000]

    summarized = []
    for entry in network_data[:max_entries]:
        payload = entry.get("payload", entry)
        fetch_details = payload.get("fetchDetails", payload)
        summary = {
            "method": fetch_details.get("method", "?"),
            "url": fetch_details.get("url", fetch_details.get("requestURL", "?")),
            "status": fetch_details.get("status", "?"),
        }
        url = summary["url"]
        if any(ext in url for ext in [".woff", ".ttf", ".png", ".jpg", ".svg", ".css", ".ico"]):
            continue
        summarized.append(summary)

    return json.dumps(summarized, indent=2)


def _is_app_host(host: str) -> bool:
    """True if a host looks like the app under test rather than a CDN/auth/telemetry service."""
    if not host or "localhost" in host or "127.0.0.1" in host:
        return False
    host_lc = host.lower()
    if host_lc in NON_APP_HOSTS:
        return False
    return not any(host_lc == skip or host_lc.endswith("." + skip) for skip in NON_APP_HOSTS)


def _extract_base_url(details: Any, events_text: str) -> str:
    """Detect the app's base URL by picking the most-referenced non-CDN host."""
    host_counts: dict[str, int] = {}

    for url in re.findall(r'https?://[^"\s\'<>]+', events_text or ""):
        try:
            host = urlparse(url).netloc
        except ValueError:
            continue
        if _is_app_host(host):
            host_counts[host] = host_counts.get(host, 0) + 1

    if isinstance(details, dict):
        network_hosts = details.get("eventsSummary", {}).get("network", {}).get("host", {})
        if isinstance(network_hosts, dict):
            for host, count in network_hosts.items():
                if _is_app_host(host):
                    host_counts[host] = host_counts.get(host, 0) + int(count or 0)

    if host_counts:
        best_host = max(host_counts.items(), key=lambda item: item[1])[0]
        return f"https://{best_host}"

    if isinstance(details, dict):
        url = details.get("url")
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            return url

    return "http://localhost:3000"


async def fetch_jam_recording(jam_url: str, token: Optional[str] = None) -> dict:
    tok = token or JAM_ACCESS_TOKEN
    if not tok:
        raise ValueError("JAM_ACCESS_TOKEN is required")

    jam_link = extract_jam_id(jam_url)
    if not jam_link:
        raise ValueError("Invalid Jam URL. Expected format: https://jam.dev/c/<id>")

    log.info(f"Fetching Jam recording: {jam_link}")

    mcp = JamMCPClient(tok)

    # Order matters — analyzeVideo is the highest-signal source (Jam's own LLM
    # analysis with video context) but also the slowest, so we run everything in
    # parallel and let the fast ones return early.
    tool_names = ["getDetails", "getUserEvents", "getConsoleLogs", "getNetworkRequests", "analyzeVideo"]

    async def _call(client_ref: httpx.AsyncClient, tool: str) -> Any:
        try:
            return await mcp.call_tool(client_ref, tool, {"jamId": jam_link})
        except JamAuthError:
            raise
        except Exception as e:
            log.error(f"Jam MCP {tool} failed: {e}")
            return e

    async with httpx.AsyncClient(timeout=180) as client:
        # We must establish the MCP session first — call one tool sequentially
        # so _ensure_session runs, then fire the rest in parallel.
        first_result = await _call(client, tool_names[0])
        rest_results = await asyncio.gather(*[_call(client, t) for t in tool_names[1:]])
        results: list[Any] = [first_result, *rest_results]

    if all(isinstance(r, Exception) for r in results):
        raise JamFetchError(
            "All Jam MCP tool calls failed — recording could not be fetched. "
            "Verify the Jam URL is valid and that JAM_ACCESS_TOKEN has access to it."
        )

    details = results[0] if not isinstance(results[0], Exception) else None
    events = results[1] if not isinstance(results[1], Exception) else None
    console = results[2] if not isinstance(results[2], Exception) else None
    network = results[3] if not isinstance(results[3], Exception) else None
    analysis = results[4] if not isinstance(results[4], Exception) else None

    log.info(
        f"Jam fetch: details={not isinstance(results[0], Exception)}, "
        f"events={not isinstance(results[1], Exception)}, "
        f"console={not isinstance(results[2], Exception)}, "
        f"network={not isinstance(results[3], Exception)}, "
        f"analysis={not isinstance(results[4], Exception)}"
    )

    # Events might be a string (narrative) rather than a list
    events_text = ""
    events_list = []
    if isinstance(events, str):
        events_text = events
    elif isinstance(events, list):
        events_list = events
    elif isinstance(events, dict):
        events_text = json.dumps(events, indent=2)

    # Extract the actual base URL from recording data
    meta_url = _extract_base_url(details, events_text)
    log.info(f"Extracted base URL: {meta_url}")

    # Console might also be a string
    console_text = ""
    if isinstance(console, str):
        console_text = console
    elif isinstance(console, list):
        console_text = json.dumps(console, indent=2)
    elif isinstance(console, dict):
        console_text = json.dumps(console, indent=2)

    details_dict = details if isinstance(details, dict) else {}

    recording = {
        "events": events_list,
        "eventsText": events_text,
        "consoleLogs": console_text,
        "networkRequests": network,
        "details": details,
        "analysis": analysis,
        "metadata": {
            "url": meta_url,
            "title": details_dict.get("title") if details_dict else None,
            "duration": details_dict.get("duration") if details_dict else None,
        },
        "sources": {
            "details": not isinstance(results[0], Exception),
            "userEvents": not isinstance(results[1], Exception),
            "consoleLogs": not isinstance(results[2], Exception),
            "networkRequests": not isinstance(results[3], Exception),
            "analysis": not isinstance(results[4], Exception) and analysis is not None,
        },
    }

    log.info(
        f"Recording assembled: events={'text' if events_text else len(events_list)}, "
        f"console={len(console_text)} chars, network={'present' if network else 'none'}"
    )

    return recording


# Markers that make a CSS selector "stable enough to trust" — an id, a data-*
# attribute, a role/aria attribute, an input type/name, a href match, or a
# structural pseudo-class like :has-text. A selector containing any of these
# is kept; a selector that's purely tag+classes is dropped as a class salad.
_STABILITY_MARKERS = (
    "#",
    "[data-",
    "[aria-",
    "[role=",
    "[type=",
    "[name=",
    "[id=",
    "[href",
    ":has-text(",
    ":has(",
    ":nth-",
    ":first-",
    ":last-",
    ":only-",
)

_NON_EDITABLE_ROLES = {"button", "link", "switch", "checkbox", "menuitem", "tab"}


def _looks_like_class_salad(css: str) -> bool:
    """
    True if the CSS has no stable identifier — just a tag and a bunch of
    classes. In modern React/tailwind apps, class-only selectors match dozens
    to hundreds of elements and are strictly worse than a semantic locator.
    """
    if not css:
        return False
    stripped = css.strip()
    if any(marker in stripped for marker in _STABILITY_MARKERS):
        return False
    # No stability marker; if there's a class token anywhere in the selector,
    # this is a class salad.
    return "." in stripped


def _sanitize_intent_selectors(parsed: dict) -> tuple[dict, int]:
    """
    Post-process the LLM output to strip class-salad CSS selectors that would
    match hundreds of elements. Returns the sanitized dict and a count of
    selectors stripped, for observability.
    """
    stripped = 0
    for step in parsed.get("steps", []):
        target = step.get("target")
        if not isinstance(target, dict):
            continue
        css = target.get("css")
        if isinstance(css, str) and _looks_like_class_salad(css):
            log.warning(f"Stripped class-salad css from step {step.get('id')}: {css!r}")
            target["css"] = None
            stripped += 1
    return parsed, stripped


def _intent_quality_issues(parsed: dict) -> list[str]:
    """
    Heuristic quality checks for generated intents.

    These are intentionally conservative and target high-probability failures
    that cause users to regenerate repeatedly (ambiguous targets, class-salad
    selectors, non-editable locators for type steps, contradictory URL asserts).
    """
    issues: list[str] = []
    steps = parsed.get("steps")
    assertions = parsed.get("assertions")

    if not isinstance(steps, list) or not steps:
        return ["No steps were generated."]

    if not isinstance(assertions, list):
        assertions = []

    for idx, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            issues.append(f"Step {idx} is not a valid object.")
            continue
        step_id = step.get("id", f"step-{idx}")
        step_type = step.get("type")
        target = step.get("target")

        needs_target = step_type in {"click", "type", "select", "hover", "scroll"}
        if needs_target and not isinstance(target, dict):
            issues.append(f"{step_id}: {step_type} step is missing a target object.")
            continue
        if not isinstance(target, dict):
            continue

        css = target.get("css")
        if isinstance(css, str) and _looks_like_class_salad(css):
            issues.append(f"{step_id}: target.css is a class-salad selector ({css!r}).")

        if step_type == "type":
            role = str(target.get("role") or "").strip().lower()
            if role in _NON_EDITABLE_ROLES:
                issues.append(f"{step_id}: type target role={role!r} is non-editable.")
            if not any(target.get(k) for k in ("testId", "css", "label", "placeholder")):
                text = target.get("text")
                if isinstance(text, str) and text.strip():
                    issues.append(f"{step_id}: type target relies only on text={text!r}; add label/placeholder/css/testId.")

    # Contradictory URL assertions after the same step are a frequent LLM error.
    url_by_step: dict[str, set[str]] = {}
    for a in assertions:
        if not isinstance(a, dict):
            continue
        if a.get("type") != "url":
            continue
        after = a.get("afterStep")
        expected = a.get("expected")
        if not isinstance(after, str) or not isinstance(expected, str):
            continue
        url_by_step.setdefault(after, set()).add(expected)
    for after_step, expected_set in url_by_step.items():
        if len(expected_set) > 1:
            issues.append(
                f"{after_step}: contradictory URL assertions {sorted(expected_set)}; keep only the final settled URL."
            )

    return issues


async def _repair_intent_with_claude(
    client: anthropic.Anthropic,
    parsed: dict,
    issues: list[str],
    effective_base: str,
) -> dict:
    """
    Ask Claude to minimally repair an already-generated intent.
    """
    repair_prompt = (
        "You previously generated a test intent. It has reliability issues.\n\n"
        f"Base URL: {effective_base}\n\n"
        "Issues to fix:\n"
        + "\n".join(f"- {issue}" for issue in issues)
        + "\n\nCurrent intent JSON:\n"
        + json.dumps(parsed, indent=2)
        + "\n\n"
        "Return a corrected intent by calling emit_test_intent.\n"
        "Keep the same user journey, preserve step order where possible, and only change what is needed to fix issues."
    )

    repaired_response = await _call_claude_with_retry(
        client,
        model=CONVERTER_MODEL,
        max_tokens=CONVERTER_MAX_TOKENS,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        tools=[INTENT_TOOL_SCHEMA],
        tool_choice={"type": "tool", "name": "emit_test_intent"},
        messages=[{"role": "user", "content": repair_prompt}],
    )

    tool_block = next((b for b in repaired_response.content if getattr(b, "type", None) == "tool_use"), None)
    if tool_block is None or not isinstance(tool_block.input, dict):
        stop_reason = getattr(repaired_response, "stop_reason", "?")
        raise RuntimeError(f"Claude repair pass did not emit a tool call (stop_reason={stop_reason})")
    return tool_block.input


def _is_transient_error(exc: BaseException) -> bool:
    """Anthropic errors worth retrying: rate-limits, timeouts, connection issues, 5xx."""
    if isinstance(exc, (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.APITimeoutError)):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        status = getattr(exc, "status_code", None)
        return status is not None and status >= 500
    return False


async def _call_claude_with_retry(client: anthropic.Anthropic, **kwargs: Any):
    """Sync Anthropic SDK call wrapped with exponential-backoff retry on transient errors."""
    last_exc: BaseException | None = None
    for attempt in range(1, CONVERTER_MAX_RETRIES + 1):
        try:
            return await asyncio.to_thread(client.messages.create, **kwargs)
        except BaseException as exc:
            last_exc = exc
            if not _is_transient_error(exc) or attempt == CONVERTER_MAX_RETRIES:
                raise
            delay = (2 ** (attempt - 1)) + random.uniform(0, 0.5)
            log.warning(f"Claude call failed (attempt {attempt}/{CONVERTER_MAX_RETRIES}): {exc}. Retrying in {delay:.1f}s")
            await asyncio.sleep(delay)
    raise last_exc  # unreachable but keeps type checkers happy


async def convert_jam_recording(
    recording: dict,
    base_url: Optional[str] = None,
    test_name: Optional[str] = None,
) -> TestIntent:
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is required")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    effective_base = base_url or recording.get("metadata", {}).get("url", "http://localhost:3000")

    events_str = recording.get("eventsText", "")
    if not events_str and recording.get("events"):
        events_str = json.dumps(recording["events"], indent=2)
    if not events_str:
        events_str = "No user events captured"

    console_str = recording.get("consoleLogs", "") or "No console logs captured"

    network_str = _summarize_network_requests(recording.get("networkRequests"))

    details = recording.get("details")
    if isinstance(details, dict):
        details_str = json.dumps(details, indent=2)
    elif isinstance(details, str):
        details_str = details
    else:
        details_str = "No recording details available"

    analysis = recording.get("analysis")
    if isinstance(analysis, (list, dict)):
        analysis_str = json.dumps(analysis, indent=2)
    elif isinstance(analysis, str):
        analysis_str = analysis
    else:
        analysis_str = "No Jam analysis available — rely on raw events below."

    user_prompt = USER_TEMPLATE.format(
        baseUrl=effective_base,
        details=details_str,
        analysis=analysis_str,
        events=events_str,
        consoleLogs=console_str,
        networkRequests=network_str,
    )

    log.info(f"Sending to Claude: system_len={len(SYSTEM_PROMPT)}, user_len={len(user_prompt)}, base_url={effective_base}")

    response = await _call_claude_with_retry(
        client,
        model=CONVERTER_MODEL,
        max_tokens=CONVERTER_MAX_TOKENS,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        tools=[INTENT_TOOL_SCHEMA],
        tool_choice={"type": "tool", "name": "emit_test_intent"},
        messages=[{"role": "user", "content": user_prompt}],
    )

    usage = getattr(response, "usage", None)
    if usage is not None:
        log.info(
            f"Claude usage: input={getattr(usage, 'input_tokens', '?')}, "
            f"output={getattr(usage, 'output_tokens', '?')}, "
            f"cache_read={getattr(usage, 'cache_read_input_tokens', 0)}, "
            f"cache_write={getattr(usage, 'cache_creation_input_tokens', 0)}"
        )

    tool_block = next((b for b in response.content if getattr(b, "type", None) == "tool_use"), None)
    if tool_block is None or not isinstance(tool_block.input, dict):
        stop_reason = getattr(response, "stop_reason", "?")
        raise RuntimeError(f"Claude did not emit a tool call (stop_reason={stop_reason})")

    parsed = tool_block.input

    parsed, stripped = _sanitize_intent_selectors(parsed)
    issues = _intent_quality_issues(parsed)
    repair_passes = 0
    while issues and repair_passes < CONVERTER_REPAIR_PASSES:
        repair_passes += 1
        log.warning(
            f"Intent quality issues detected (pass {repair_passes}/{CONVERTER_REPAIR_PASSES}): "
            + "; ".join(issues[:8])
        )
        parsed = await _repair_intent_with_claude(client, parsed, issues, effective_base)
        parsed, stripped_now = _sanitize_intent_selectors(parsed)
        stripped += stripped_now
        issues = _intent_quality_issues(parsed)
    if issues:
        log.warning("Intent still has unresolved quality issues after repair: " + "; ".join(issues[:8]))

    log.info(
        f"Claude generated: {len(parsed.get('steps', []))} steps, "
        f"{len(parsed.get('assertions', []))} assertions, "
        f"stripped {stripped} class-salad css selectors, "
        f"repair_passes={repair_passes}"
    )

    test_id = f"test-{uuid.uuid4().hex[:8]}"

    intent_data = {
        "id": test_id,
        "name": test_name or parsed.get("name", "Converted Jam Recording"),
        "description": parsed.get("description", "Test converted from Jam recording"),
        "baseUrl": effective_base,
        "createdFrom": "recorder",
        "tags": parsed.get("tags", ["converted", "jam"]),
        "steps": parsed.get("steps", []),
        "assertions": parsed.get("assertions", []),
        "config": {"timeout": 30000, "retries": 1, "viewport": {"width": 1280, "height": 720}, "browsers": ["chromium"]},
    }

    intent = TestIntent.model_validate(intent_data)
    return intent


async def save_intent(intent: TestIntent, output_dir: Optional[Path] = None) -> str:
    out = output_dir or INTENTS_DIR
    out.mkdir(parents=True, exist_ok=True)
    filepath = out / f"{intent.id}.json"
    filepath.write_text(json.dumps(intent.model_dump(by_alias=True), indent=2))
    log.info(f"Intent saved: {filepath}")
    return str(filepath)
