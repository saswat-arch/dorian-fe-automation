from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from playwright.async_api import Locator, Page


@dataclass
class ParsedLocator:
    method: str
    args: list[Any]
    chain_methods: list[dict[str, Any]] = field(default_factory=list)


_LOCATOR_PATTERNS: list[tuple[re.Pattern, str, Any]] = [
    (re.compile(r"^getByTestId\(['\"](.+)['\"]\)$"), "get_by_test_id", lambda m: [m.group(1)]),
    (
        re.compile(r"^getByRole\(['\"](\w+)['\"](?:,\s*\{\s*name:\s*['\"](.+)['\"]\s*\})?\)$"),
        "get_by_role",
        lambda m: [m.group(1), {"name": m.group(2)}] if m.group(2) else [m.group(1)],
    ),
    (re.compile(r"^getByLabel\(['\"](.+)['\"]\)$"), "get_by_label", lambda m: [m.group(1)]),
    (re.compile(r"^getByPlaceholder\(['\"](.+)['\"]\)$"), "get_by_placeholder", lambda m: [m.group(1)]),
    (
        re.compile(r"^getByText\(['\"](.+)['\"](?:,\s*\{\s*exact:\s*(true|false)\s*\})?\)$"),
        "get_by_text",
        lambda m: [m.group(1), {"exact": m.group(2) == "true"}] if m.group(2) else [m.group(1)],
    ),
    (re.compile(r"^getByAltText\(['\"](.+)['\"]\)$"), "get_by_alt_text", lambda m: [m.group(1)]),
    (re.compile(r"^getByTitle\(['\"](.+)['\"]\)$"), "get_by_title", lambda m: [m.group(1)]),
    (re.compile(r"^locator\(['\"](.+)['\"]\)$"), "locator", lambda m: [m.group(1)]),
]

_CHAIN_PATTERNS: list[tuple[re.Pattern, str, Any]] = [
    (re.compile(r"\.first\(\)$"), "first", lambda _m: []),
    (re.compile(r"\.last\(\)$"), "last", lambda _m: []),
    (re.compile(r"\.nth\((\d+)\)$"), "nth", lambda m: [int(m.group(1))]),
    (re.compile(r"\.filter\(\{\s*hasText:\s*['\"](.+)['\"]\s*\}\)$"), "filter", lambda m: [{"has_text": m.group(1)}]),
]


def parse_locator_string(locator_str: str) -> ParsedLocator | None:
    trimmed = locator_str.strip()
    chain_methods: list[dict[str, Any]] = []
    base = trimmed

    for pattern, method, extract in _CHAIN_PATTERNS:
        match = pattern.search(base)
        if match:
            chain_methods.insert(0, {"method": method, "args": extract(match)})
            base = pattern.sub("", base)

    for pattern, method, extract in _LOCATOR_PATTERNS:
        match = pattern.match(base)
        if match:
            return ParsedLocator(method=method, args=extract(match), chain_methods=chain_methods)

    return None


def execute_locator(page: Page, locator_str: str) -> Locator | None:
    parsed = parse_locator_string(locator_str)
    if not parsed:
        return None

    method_map = {
        "get_by_test_id": page.get_by_test_id,
        "get_by_label": page.get_by_label,
        "get_by_placeholder": page.get_by_placeholder,
        "get_by_alt_text": page.get_by_alt_text,
        "get_by_title": page.get_by_title,
        "locator": page.locator,
    }

    if parsed.method == "get_by_role":
        if len(parsed.args) > 1 and isinstance(parsed.args[1], dict):
            loc = page.get_by_role(parsed.args[0], name=parsed.args[1].get("name"))
        else:
            loc = page.get_by_role(parsed.args[0])
    elif parsed.method == "get_by_text":
        if len(parsed.args) > 1 and isinstance(parsed.args[1], dict):
            loc = page.get_by_text(parsed.args[0], exact=parsed.args[1].get("exact", False))
        else:
            loc = page.get_by_text(parsed.args[0])
    elif parsed.method in method_map:
        loc = method_map[parsed.method](parsed.args[0])
    else:
        return None

    for chain in parsed.chain_methods:
        if chain["method"] == "first":
            loc = loc.first
        elif chain["method"] == "last":
            loc = loc.last
        elif chain["method"] == "nth":
            loc = loc.nth(chain["args"][0])
        elif chain["method"] == "filter":
            loc = loc.filter(**chain["args"][0])

    return loc


def is_valid_locator_string(locator_str: str) -> bool:
    return parse_locator_string(locator_str) is not None


def sanitize_ai_response(response: str) -> str:
    cleaned = response.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```\w*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    if cleaned.startswith("page."):
        cleaned = cleaned[5:]
    cleaned = cleaned.rstrip(";")
    return cleaned.strip()
