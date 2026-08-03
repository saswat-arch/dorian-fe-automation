from __future__ import annotations

import sqlite3
from pathlib import Path

from engine.config import DB_PATH
from engine.utils.logger import create_logger

log = create_logger("knowledgebase-db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
  path TEXT PRIMARY KEY,
  title TEXT,
  last_seen TEXT,
  visit_count INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS components (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  page_path TEXT REFERENCES pages(path),
  tag TEXT,
  role TEXT,
  test_id TEXT,
  text TEXT,
  label TEXT,
  type TEXT,
  placeholder TEXT,
  last_seen TEXT
);

CREATE TABLE IF NOT EXISTS navigation (
  from_path TEXT REFERENCES pages(path),
  to_path TEXT REFERENCES pages(path),
  trigger TEXT,
  last_seen TEXT,
  PRIMARY KEY (from_path, to_path, trigger)
);

CREATE TABLE IF NOT EXISTS api_endpoints (
  method TEXT,
  url_pattern TEXT,
  last_status INTEGER,
  last_seen TEXT,
  PRIMARY KEY (method, url_pattern)
);

CREATE INDEX IF NOT EXISTS idx_components_page ON components(page_path);
CREATE INDEX IF NOT EXISTS idx_components_test_id ON components(test_id);
CREATE INDEX IF NOT EXISTS idx_navigation_from ON navigation(from_path);
"""

_db: sqlite3.Connection | None = None


def get_database(db_path: str | Path | None = None) -> sqlite3.Connection:
    global _db
    if _db is not None:
        return _db

    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    _db = sqlite3.connect(str(path))
    _db.row_factory = sqlite3.Row
    _db.execute("PRAGMA journal_mode = WAL")
    _db.executescript(SCHEMA)
    log.debug(f"Database initialized: {path}")
    return _db


def close_database() -> None:
    global _db
    if _db:
        _db.close()
        _db = None


def upsert_page(db: sqlite3.Connection, path: str, title: str | None, last_seen: str, visit_count: int = 1) -> None:
    db.execute(
        """INSERT INTO pages (path, title, last_seen, visit_count) VALUES (?, ?, ?, ?)
           ON CONFLICT(path) DO UPDATE SET title = COALESCE(?, title), last_seen = ?, visit_count = visit_count + 1""",
        (path, title, last_seen, visit_count, title, last_seen),
    )
    db.commit()


def upsert_component(db: sqlite3.Connection, **kwargs) -> None:
    existing = db.execute(
        "SELECT id FROM components WHERE page_path = ? AND tag = ? AND COALESCE(test_id, '') = COALESCE(?, '') AND COALESCE(text, '') = COALESCE(?, '')",
        (kwargs["page_path"], kwargs["tag"], kwargs.get("test_id"), kwargs.get("text")),
    ).fetchone()

    if existing:
        db.execute(
            "UPDATE components SET role=COALESCE(?,role), label=COALESCE(?,label), type=COALESCE(?,type), placeholder=COALESCE(?,placeholder), last_seen=? WHERE id=?",
            (kwargs.get("role"), kwargs.get("label"), kwargs.get("type"), kwargs.get("placeholder"), kwargs["last_seen"], existing["id"]),
        )
    else:
        db.execute(
            "INSERT INTO components (page_path,tag,role,test_id,text,label,type,placeholder,last_seen) VALUES (?,?,?,?,?,?,?,?,?)",
            (kwargs["page_path"], kwargs["tag"], kwargs.get("role"), kwargs.get("test_id"), kwargs.get("text"), kwargs.get("label"), kwargs.get("type"), kwargs.get("placeholder"), kwargs["last_seen"]),
        )
    db.commit()


def upsert_navigation(db: sqlite3.Connection, from_path: str, to_path: str, trigger: str, last_seen: str) -> None:
    db.execute(
        """INSERT INTO navigation (from_path, to_path, trigger, last_seen) VALUES (?, ?, ?, ?)
           ON CONFLICT(from_path, to_path, trigger) DO UPDATE SET last_seen = ?""",
        (from_path, to_path, trigger, last_seen, last_seen),
    )
    db.commit()


def upsert_api_endpoint(db: sqlite3.Connection, method: str, url_pattern: str, last_status: int | None, last_seen: str) -> None:
    db.execute(
        """INSERT INTO api_endpoints (method, url_pattern, last_status, last_seen) VALUES (?, ?, ?, ?)
           ON CONFLICT(method, url_pattern) DO UPDATE SET last_status = ?, last_seen = ?""",
        (method, url_pattern, last_status, last_seen, last_status, last_seen),
    )
    db.commit()
