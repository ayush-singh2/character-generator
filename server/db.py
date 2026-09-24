"""SQLite index for projects.

Heavy artifacts (manuscripts, reference sheets, page renders, the PDF) live on
the filesystem under books/<slug>/ exactly as the pipeline expects. This index
only holds the lightweight metadata the Home dashboard needs to list, sort and
search projects, plus the New Project draft (style/size/typography/palette) and
per-project settings as JSON blobs.
"""

import json
import os
import sqlite3
import threading
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# DB lives under STATE_DIR (a persistent disk in production; the repo locally).
STATE_DIR = os.environ.get("BB_STATE_DIR", REPO)
DATA_DIR = os.path.join(STATE_DIR, "server", "data")
DB_PATH = os.path.join(DATA_DIR, "app.db")

_local = threading.local()

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,
    slug        TEXT UNIQUE NOT NULL,
    title       TEXT NOT NULL,
    author      TEXT DEFAULT '',
    status      TEXT DEFAULT 'Draft',        -- Draft | In Progress | Complete
    book_type   TEXT DEFAULT '',             -- illustration style label
    pages       INTEGER DEFAULT 0,
    style       TEXT DEFAULT '',             -- chosen style label
    tags        TEXT DEFAULT '[]',           -- json array
    draft_json  TEXT DEFAULT '{}',           -- New Project form state
    settings_json TEXT DEFAULT '{}',
    progress    INTEGER DEFAULT 0,           -- 0..100 (mirrors last job)
    stage       TEXT DEFAULT '',             -- last known pipeline stage
    created_ts  INTEGER NOT NULL,
    edited_ts   INTEGER NOT NULL
);
"""


def _conn():
    c = getattr(_local, "conn", None)
    if c is None:
        os.makedirs(DATA_DIR, exist_ok=True)
        c = sqlite3.connect(DB_PATH)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript(SCHEMA)
        _local.conn = c
    return c


def now_ms():
    return int(time.time() * 1000)


def _row_to_project(r):
    d = dict(r)
    d["tags"] = json.loads(d.get("tags") or "[]")
    d["draft"] = json.loads(d.pop("draft_json", "{}") or "{}")
    d["settings"] = json.loads(d.pop("settings_json", "{}") or "{}")
    return d


def list_projects():
    rows = _conn().execute("SELECT * FROM projects ORDER BY edited_ts DESC").fetchall()
    return [_row_to_project(r) for r in rows]


def get_project(pid):
    r = _conn().execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    return _row_to_project(r) if r else None


def get_by_slug(slug):
    r = _conn().execute("SELECT * FROM projects WHERE slug=?", (slug,)).fetchone()
    return _row_to_project(r) if r else None


def create_project(pid, slug, title, **fields):
    ts = now_ms()
    cols = dict(
        id=pid, slug=slug, title=title,
        author=fields.get("author", ""),
        status=fields.get("status", "Draft"),
        book_type=fields.get("book_type", ""),
        pages=int(fields.get("pages", 0) or 0),
        style=fields.get("style", ""),
        tags=json.dumps(fields.get("tags", [])),
        draft_json=json.dumps(fields.get("draft", {})),
        settings_json=json.dumps(fields.get("settings", {})),
        created_ts=ts, edited_ts=ts,
    )
    ph = ",".join("?" for _ in cols)
    _conn().execute(
        f"INSERT INTO projects ({','.join(cols)}) VALUES ({ph})",
        tuple(cols.values()),
    )
    _conn().commit()
    return get_project(pid)


def update_project(pid, **fields):
    if not fields:
        return get_project(pid)
    # serialize known json fields
    if "tags" in fields and not isinstance(fields["tags"], str):
        fields["tags"] = json.dumps(fields["tags"])
    if "draft" in fields:
        fields["draft_json"] = json.dumps(fields.pop("draft"))
    if "settings" in fields:
        fields["settings_json"] = json.dumps(fields.pop("settings"))
    fields["edited_ts"] = now_ms()
    sets = ",".join(f"{k}=?" for k in fields)
    _conn().execute(f"UPDATE projects SET {sets} WHERE id=?",
                    tuple(fields.values()) + (pid,))
    _conn().commit()
    return get_project(pid)


def delete_project(pid):
    _conn().execute("DELETE FROM projects WHERE id=?", (pid,))
    _conn().commit()
