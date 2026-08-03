from __future__ import annotations

from playwright.async_api import Page

STRIP_TAGS = {"style", "script", "svg", "noscript", "link", "meta", "head"}
KEEP_ATTRIBUTES = {
    "id", "data-testid", "role", "aria-label", "aria-describedby",
    "type", "name", "placeholder", "href", "src", "alt", "value",
    "action", "method", "for", "title",
}

DEFAULT_MAX_DEPTH = 4
DEFAULT_MAX_LENGTH = 8000
DEFAULT_MAX_TEXT_LENGTH = 50


def _node_to_string(node: dict, indent: int = 0) -> str:
    spaces = "  " * indent
    attrs_str = " ".join(f'{k}="{v}"' for k, v in node.get("attrs", {}).items())
    tag = node["tag"]
    text = node.get("text", "")
    children = node.get("children", [])

    result = f"{spaces}<{tag}{' ' + attrs_str if attrs_str else ''}>"
    if text:
        result += text
    if children:
        result += "\n"
        for child in children:
            result += _node_to_string(child, indent + 1) + "\n"
        result += f"{spaces}</{tag}>"
    elif text:
        result += f"</{tag}>"
    else:
        result = f"{spaces}<{tag}{' ' + attrs_str if attrs_str else ''} />"
    return result


async def extract_dom_snapshot(
    page: Page,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_length: int = DEFAULT_MAX_LENGTH,
    max_text_length: int = DEFAULT_MAX_TEXT_LENGTH,
) -> str:
    serialized = await page.evaluate(
        """([maxDepth, maxTextLen, stripTags, keepAttrs]) => {
            const STRIP = new Set(stripTags);
            const KEEP = new Set(keepAttrs);
            function filterAttrs(el) {
                const f = {};
                for (let i = 0; i < el.attributes.length; i++) {
                    const a = el.attributes[i];
                    if (KEEP.has(a.name) || a.name.startsWith('data-testid') || a.name.startsWith('aria-'))
                        f[a.name] = a.value;
                }
                return f;
            }
            function truncate(t, max) {
                const s = t.trim().replace(/\\s+/g, ' ');
                return s.length <= max ? s : s.slice(0, max) + '...';
            }
            function ser(el, depth) {
                const tag = el.tagName.toLowerCase();
                if (STRIP.has(tag)) return null;
                const node = { tag, attrs: filterAttrs(el) };
                let text = '';
                for (let i = 0; i < el.childNodes.length; i++) {
                    if (el.childNodes[i].nodeType === 3) text += el.childNodes[i].textContent || '';
                }
                text = text.trim();
                if (text) node.text = truncate(text, maxTextLen);
                if (depth < maxDepth) {
                    const ch = [];
                    for (let i = 0; i < el.children.length; i++) {
                        const s = ser(el.children[i], depth + 1);
                        if (s) ch.push(s);
                    }
                    if (ch.length) node.children = ch;
                }
                return node;
            }
            return document.body ? ser(document.body, 0) : null;
        }""",
        [max_depth, max_text_length, list(STRIP_TAGS), list(KEEP_ATTRIBUTES)],
    )

    if not serialized:
        return "<body />"

    result = _node_to_string(serialized)
    if len(result) > max_length:
        result = result[:max_length] + "\n... (truncated)"
    return result
