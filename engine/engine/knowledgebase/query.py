from __future__ import annotations

from engine.knowledgebase.db import get_database
from engine.utils.logger import create_logger

log = create_logger("kb-query")


def get_page_info(path: str, db_path: str | None = None) -> dict | None:
    db = get_database(db_path)
    row = db.execute("SELECT path, title, last_seen, visit_count FROM pages WHERE path = ?", (path,)).fetchone()
    return dict(row) if row else None


def get_all_pages(limit: int = 50, db_path: str | None = None) -> list[dict]:
    db = get_database(db_path)
    rows = db.execute("SELECT path, title, last_seen, visit_count FROM pages ORDER BY visit_count DESC, last_seen DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_components_on_page(path: str, limit: int = 50, db_path: str | None = None) -> list[dict]:
    db = get_database(db_path)
    rows = db.execute(
        "SELECT * FROM components WHERE page_path = ? ORDER BY CASE WHEN test_id IS NOT NULL THEN 0 ELSE 1 END, tag LIMIT ?",
        (path, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def get_navigation_from(path: str, db_path: str | None = None) -> list[dict]:
    db = get_database(db_path)
    rows = db.execute("SELECT * FROM navigation WHERE from_path = ? ORDER BY last_seen DESC", (path,)).fetchall()
    return [dict(r) for r in rows]


def get_navigation_to(path: str, db_path: str | None = None) -> list[dict]:
    db = get_database(db_path)
    rows = db.execute("SELECT * FROM navigation WHERE to_path = ? ORDER BY last_seen DESC", (path,)).fetchall()
    return [dict(r) for r in rows]


def find_component(description: str, limit: int = 50, db_path: str | None = None) -> list[dict]:
    db = get_database(db_path)
    term = f"%{description.lower()}%"
    rows = db.execute(
        """SELECT * FROM components WHERE
           LOWER(COALESCE(text,'')) LIKE ? OR LOWER(COALESCE(label,'')) LIKE ?
           OR LOWER(COALESCE(test_id,'')) LIKE ? OR LOWER(COALESCE(placeholder,'')) LIKE ?
           LIMIT ?""",
        (term, term, term, term, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def get_api_endpoints(limit: int = 50, db_path: str | None = None) -> list[dict]:
    db = get_database(db_path)
    rows = db.execute("SELECT * FROM api_endpoints ORDER BY last_seen DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_stats(db_path: str | None = None) -> dict:
    db = get_database(db_path)
    return {
        "pageCount": db.execute("SELECT COUNT(*) FROM pages").fetchone()[0],
        "componentCount": db.execute("SELECT COUNT(*) FROM components").fetchone()[0],
        "navigationCount": db.execute("SELECT COUNT(*) FROM navigation").fetchone()[0],
        "apiEndpointCount": db.execute("SELECT COUNT(*) FROM api_endpoints").fetchone()[0],
    }


def serialize_page_context(path: str, db_path: str | None = None) -> str:
    page = get_page_info(path, db_path)
    components = get_components_on_page(path, 50, db_path)
    navigation = get_navigation_from(path, db_path)

    lines = [f"Page: {path}{' - \"' + page['title'] + '\"' if page and page.get('title') else ''}", ""]

    if components:
        lines.append("Components:")
        for c in components:
            line = f"- {c['tag']}"
            if c.get("text"):
                line += f' "{c["text"]}"'
            attrs = []
            if c.get("test_id"):
                attrs.append(f'data-testid="{c["test_id"]}"')
            if c.get("role"):
                attrs.append(f'role="{c["role"]}"')
            if c.get("type"):
                attrs.append(f'type="{c["type"]}"')
            if attrs:
                line += f" [{', '.join(attrs)}]"
            lines.append(line)
        lines.append("")

    if navigation:
        lines.append("Navigation:")
        for n in navigation:
            lines.append(f"- {n['trigger']} -> {n['to_path']}")

    return "\n".join(lines)


def serialize_knowledgebase_context(paths: list[str], db_path: str | None = None) -> str:
    return "\n\n---\n\n".join(serialize_page_context(p, db_path) for p in paths)
