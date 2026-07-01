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
    # 2 — per-(person, photo) face padding. The Gramps rect is always the
    # materialization of Immich's detected box + this pad; absence means the
    # default applies (0.15, or 0.0 on Sync/ManualFaces-tagged assets).
    """
    CREATE TABLE face_pads (
        gramps_handle TEXT NOT NULL,
        asset_id      TEXT NOT NULL,
        pad           REAL NOT NULL,
        updated_at    TEXT NOT NULL,
        PRIMARY KEY (gramps_handle, asset_id)
    );
    """,
    # 3 — UI-generated media-id reservations. Codes minted ahead of time in the
    # ID-generator tab are reserved here so the auto-generator never reuses them;
    # manual id entry at sync time DOES accept a reserved id. minted_at flips when
    # the id is actually created in Gramps.
    """
    CREATE TABLE reserved_ids (
        gramps_id  TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        minted_at  TEXT,
        note       TEXT
    );
    """,
    # 4 — Gemini OCR ledger. A doc is (re-)OCR'd only when not already recorded
    # here (or on force), so a run doesn't re-spend Gemini on every pass.
    """
    CREATE TABLE ocr_state (
        paperless_id INTEGER PRIMARY KEY,
        model        TEXT NOT NULL,
        chars        INTEGER NOT NULL,
        ocr_at       TEXT NOT NULL
    );
    """,
    # 5 — manual "assigned" step between reserved and minted. Set when Peter has
    # physically labelled a photo (verso) with a reserved id but hasn't yet synced
    # it into Gramps. Purely a Bifrost-side flag; cleared on unassign, moot once
    # minted_at flips.
    """
    ALTER TABLE reserved_ids ADD COLUMN assigned_at TEXT;
    """,
    # 6 — Immich image versioning (docs/IMMICH_VERSIONING.md). An Immich STACK is
    # one logical photo's version set; the stack's primaryAssetId is the version
    # displayed in Gramps. Versioning is a Bifrost-owned pointer layer because
    # Immich assets are immutable (each version is a separate asset id) — so the
    # change signal is "a different asset became primary", NOT a checksum drift
    # (contrast doc_versions, which diffs a mutating checksum on a stable id).
    # Durable/load-bearing state (membership, displayed=primaryAssetId, role tags)
    # lives in IMMICH; these tables are a rebuildable cache + Bifrost-owned soft
    # notes/ordering. The stable Gramps base id/handle never move — only the
    # media's path/mime/Immich-ID attribute repoint.
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
    # 7 — the a-series scan register (archive-scheme/SCHEME.md §2). One row per
    # capture FILE (recto scan, verso scan, re-scan: each its own number),
    # numbered a000101 upward in scanning order. Append-only LOG, not a catalog:
    # numbers are never reused and a deleted scan leaves a permanent gap. Object
    # identity lives in the random-6 id (reserved_ids/Gramps); physical location
    # in the call number. The b-series belongs to a different family tree and is
    # not tracked here.
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
