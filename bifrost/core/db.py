"""SQLite access and schema migrations.

Single-user app: plain sqlite3 in WAL mode is plenty. MIGRATIONS is append-only;
each entry runs once, tracked by schema_version.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

MIGRATIONS: list[str] = [
    # 1 — initial schema (docs/DESIGN.md §4)
    """
    CREATE TABLE person_links (
        gramps_handle    TEXT NOT NULL,
        immich_person_id TEXT NOT NULL,
        label            TEXT,
        created_at       TEXT NOT NULL,
        PRIMARY KEY (gramps_handle, immich_person_id)
    );

    CREATE TABLE minted_media (
        gramps_id     TEXT PRIMARY KEY,
        source_system TEXT NOT NULL CHECK (source_system IN ('immich','paperless')),
        source_id     TEXT NOT NULL,
        title         TEXT,
        minted_at     TEXT NOT NULL
    );

    CREATE TABLE doc_versions (
        paperless_id INTEGER PRIMARY KEY,
        checksum     TEXT NOT NULL,
        gramps_id    TEXT,
        updated_at   TEXT NOT NULL
    );

    CREATE TABLE transcription_state (
        paperless_id        INTEGER PRIMARY KEY,
        content_hash        TEXT NOT NULL,
        note_handle         TEXT,
        gramps_note_id      TEXT,
        gramps_media_id     TEXT,
        translation_handle  TEXT,
        translation_note_id TEXT,
        updated_at          TEXT NOT NULL
    );

    CREATE TABLE runs (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        job         TEXT NOT NULL,
        status      TEXT NOT NULL,
        started_at  TEXT NOT NULL,
        finished_at TEXT,
        summary     TEXT
    );

    CREATE TABLE run_events (
        run_id  INTEGER NOT NULL REFERENCES runs(id),
        seq     INTEGER NOT NULL,
        ts      TEXT NOT NULL,
        payload TEXT NOT NULL,
        PRIMARY KEY (run_id, seq)
    );
    """,
]


def connect(db_path: Path) -> sqlite3.Connection:
    """Open (creating if needed), migrate to latest, return the connection."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)"
    )
    row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    current = row["v"] or 0
    for number, script in enumerate(MIGRATIONS, start=1):
        if number > current:
            with conn:
                conn.executescript(script)
                conn.execute("INSERT INTO schema_version (version) VALUES (?)", (number,))
    return conn
