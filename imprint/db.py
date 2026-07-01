"""imprint/db.py — SQLite data layer (the functional-core storage).

Requirements are DATA, not a document: each requirement is a structured row that
can later be rendered as an SRS section, a user story, or a traceability-matrix
row. This module is UI-free so it can be unit-tested without launching Tkinter
(functional core / imperative shell — the same architecture as the Book Reader's
`lyceum/db/study_db.py`).
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import models


# The database lives next to the app in a `data/` folder — one local file,
# 100% offline. Override with the IMPRINT_DB_PATH env var (used by nothing yet,
# handy later for putting the data on the E: drive).
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.environ.get(
    "IMPRINT_DB_PATH", os.path.join(_PROJECT_ROOT, "data", "imprint.db")
)


def _utc_now() -> str:
    """Timestamps are stored as UTC ISO-8601 strings (sortable, timezone-safe)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- schema -----------------------------------------------------------------
# A project has many requirements. Each requirement can link to others
# (traceability). ON DELETE CASCADE keeps orphans out when a project is removed.
SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    methodology TEXT NOT NULL CHECK (methodology IN ('waterfall','vmodel','agile')),
    description TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'intake',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS requirements (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id          INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    req_key             TEXT NOT NULL,              -- human ID, e.g. REQ-0001 (unique per project)
    req_type            TEXT NOT NULL,              -- Functional / Non-Functional / Constraint / Interface
    statement           TEXT NOT NULL,
    moscow              TEXT NOT NULL DEFAULT 'Must',
    acceptance_criteria TEXT NOT NULL DEFAULT '',
    source              TEXT NOT NULL DEFAULT '',
    rationale           TEXT NOT NULL DEFAULT '',
    status              TEXT NOT NULL DEFAULT 'draft',
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    UNIQUE (project_id, req_key)
);

CREATE TABLE IF NOT EXISTS requirement_links (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    from_req   INTEGER NOT NULL REFERENCES requirements(id) ON DELETE CASCADE,
    to_req     INTEGER NOT NULL REFERENCES requirements(id) ON DELETE CASCADE,
    link_type  TEXT NOT NULL DEFAULT 'traces_to',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    role       TEXT NOT NULL,          -- 'user' or 'assistant'
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def connect(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open (creating the folder if needed) and return a configured connection."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row            # rows behave like dicts: row["name"]
    conn.execute("PRAGMA foreign_keys = ON;")  # enforce the REFERENCES above
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


@contextmanager
def transaction(conn: sqlite3.Connection):
    """Atomic unit of work: commit on success, roll back on any exception (ACID).

    Same primitive as the Book Reader's db layer — either every write inside the
    block lands, or none of them do.
    """
    try:
        conn.execute("BEGIN")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# --- projects ---------------------------------------------------------------
def create_project(
    conn: sqlite3.Connection, name: str, methodology: str, description: str = ""
) -> int:
    """Create a project and return its new id. Raises ValueError on bad input."""
    name = (name or "").strip()
    if not name:
        raise ValueError("Project name is required.")
    if not models.is_valid_methodology(methodology):
        raise ValueError(f"Unknown methodology: {methodology!r}")
    now = _utc_now()
    with transaction(conn):
        cur = conn.execute(
            "INSERT INTO projects (name, methodology, description, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, methodology, description.strip(), now, now),
        )
    return int(cur.lastrowid)


def list_projects(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM projects ORDER BY created_at DESC, id DESC"
    ).fetchall()


def get_project(conn: sqlite3.Connection, project_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM projects WHERE id = ?", (project_id,)
    ).fetchone()


# --- requirements -----------------------------------------------------------
def next_req_key(conn: sqlite3.Connection, project_id: int) -> str:
    """Compute the next human requirement ID for a project, e.g. 'REQ-0001'.

    Uses the max existing number + 1 so keys stay stable even after deletions.
    """
    rows = conn.execute(
        "SELECT req_key FROM requirements WHERE project_id = ?", (project_id,)
    ).fetchall()
    highest = 0
    for r in rows:
        key = r["req_key"]
        if "-" in key:
            try:
                highest = max(highest, int(key.split("-", 1)[1]))
            except ValueError:
                pass
    return f"REQ-{highest + 1:04d}"


def add_requirement(
    conn: sqlite3.Connection,
    project_id: int,
    req_type: str,
    statement: str,
    moscow: str = "Must",
    acceptance_criteria: str = "",
    source: str = "",
    rationale: str = "",
) -> sqlite3.Row:
    """Add a requirement to a project and return the created row.

    Raises ValueError if the statement is empty or the project doesn't exist.
    """
    statement = (statement or "").strip()
    if not statement:
        raise ValueError("Requirement statement is required.")
    if get_project(conn, project_id) is None:
        raise ValueError(f"No project with id {project_id}.")
    now = _utc_now()
    with transaction(conn):
        key = next_req_key(conn, project_id)  # inside the txn so it can't race
        cur = conn.execute(
            "INSERT INTO requirements "
            "(project_id, req_key, req_type, statement, moscow, acceptance_criteria, "
            " source, rationale, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                project_id, key, req_type, statement, moscow,
                acceptance_criteria.strip(), source.strip(), rationale.strip(),
                now, now,
            ),
        )
    return conn.execute(
        "SELECT * FROM requirements WHERE id = ?", (cur.lastrowid,)
    ).fetchone()


def list_requirements(conn: sqlite3.Connection, project_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM requirements WHERE project_id = ? ORDER BY req_key",
        (project_id,),
    ).fetchall()


def set_requirement_status(conn: sqlite3.Connection, req_id: int, status: str) -> None:
    """Update one requirement's status (e.g. 'draft' <-> 'baselined' = checked off)."""
    if status not in models.REQ_STATUSES:
        raise ValueError(f"Unknown status: {status!r}")
    now = _utc_now()
    with transaction(conn):
        conn.execute(
            "UPDATE requirements SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, req_id),
        )


# --- assistant conversation (persisted per project) -------------------------
def add_chat_message(conn: sqlite3.Connection, project_id: int, role: str, content: str) -> None:
    """Persist one line of the assistant conversation for a project."""
    with transaction(conn):
        conn.execute(
            "INSERT INTO chat_messages (project_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (project_id, role, content, _utc_now()),
        )


def list_chat_messages(conn: sqlite3.Connection, project_id: int) -> list[sqlite3.Row]:
    """The full saved conversation for a project, oldest first."""
    return conn.execute(
        "SELECT * FROM chat_messages WHERE project_id = ? ORDER BY id",
        (project_id,),
    ).fetchall()


def clear_chat_messages(conn: sqlite3.Connection, project_id: int) -> None:
    with transaction(conn):
        conn.execute("DELETE FROM chat_messages WHERE project_id = ?", (project_id,))
