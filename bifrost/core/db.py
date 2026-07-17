from __future__ import annotations

import sqlite3
from pathlib import Path

MIGRATIONS: list[str] = [
    # 1 initial
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
    # 2 (can remove at some point)
    """
    CREATE TABLE face_pads (
        gramps_handle TEXT NOT NULL,
        asset_id      TEXT NOT NULL,
        pad           REAL NOT NULL,
        updated_at    TEXT NOT NULL,
        PRIMARY KEY (gramps_handle, asset_id)
    );
    """,
    # 3 UI-generated media-id res
    """
    CREATE TABLE reserved_ids (
        gramps_id  TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        minted_at  TEXT,
        note       TEXT
    );
    """,
    # 4 Gemini OCR ledger
    """
    CREATE TABLE ocr_state (
        paperless_id INTEGER PRIMARY KEY,
        model        TEXT NOT NULL,
        chars        INTEGER NOT NULL,
        ocr_at       TEXT NOT NULL
    );
    """,
    # 5 manual "assigned"
    """
    ALTER TABLE reserved_ids ADD COLUMN assigned_at TEXT;
    """,
    # 6 Immich image versioning
    """
    CREATE TABLE immich_versions (
        gramps_id        TEXT PRIMARY KEY,
        stack_id         TEXT NOT NULL,
        current_asset_id TEXT NOT NULL,
        current_checksum TEXT NOT NULL,
        member_count     INTEGER NOT NULL,
        updated_at       TEXT NOT NULL
    );

    CREATE TABLE immich_version_members (
        gramps_id TEXT NOT NULL,
        asset_id  TEXT NOT NULL,
        checksum  TEXT NOT NULL,
        role      TEXT,
        label     TEXT,
        seq       INTEGER NOT NULL,
        PRIMARY KEY (gramps_id, asset_id)
    );
    """,
    # 7
    """
    CREATE TABLE scan_register (
        scan_no    TEXT PRIMARY KEY,
        container  TEXT,
        role       TEXT,
        object_id  TEXT,
        captured   TEXT,
        note       TEXT
    );
    """,
    # 8 UI-editable settings (photos album whitelist; was urd's settings.json)
    """
    CREATE TABLE app_settings (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """,
]


def connect(db_path: Path) -> sqlite3.Connection:
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
