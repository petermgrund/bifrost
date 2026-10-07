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
    # 5 manual assigned
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
    # 8 UI-editable settings
    """
    CREATE TABLE app_settings (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """,
    # 9 per-account person links
    """
    ALTER TABLE person_links ADD COLUMN owner_user_id TEXT;
    """,
    # 10 photo notes
    """
    CREATE TABLE photo_notes (
        asset_id       TEXT PRIMARY KEY,
        gramps_id      TEXT,
        text           TEXT NOT NULL,
        note_handle    TEXT,
        note_gramps_id TEXT,
        synced_hash    TEXT,
        updated_at     TEXT NOT NULL
    );
    """,
    # 11 photo collections with a manual order
    """
    CREATE TABLE collections (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        description TEXT,
        created_at  TEXT NOT NULL,
        updated_at  TEXT NOT NULL
    );

    CREATE TABLE collection_items (
        collection_id INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
        asset_id      TEXT NOT NULL,
        seq           INTEGER NOT NULL,
        added_at      TEXT NOT NULL,
        PRIMARY KEY (collection_id, asset_id)
    );
    """,
    # 12 per-version labels
    """
    CREATE TABLE version_labels (
        asset_id   TEXT PRIMARY KEY,
        label      TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """,
    # 13 photos whose date was set in the Photos editor
    """
    CREATE TABLE dated_photos (
        asset_id TEXT PRIMARY KEY,
        dated_at TEXT NOT NULL
    );
    """,
    # 14 collection order becomes stable slots numbered from 1
    """
    CREATE TEMP TABLE slot_ranks AS
        SELECT collection_id, asset_id,
               ROW_NUMBER() OVER (PARTITION BY collection_id ORDER BY seq, added_at, asset_id) AS slot
        FROM collection_items;
    UPDATE collection_items SET seq = (
        SELECT slot FROM slot_ranks r
        WHERE r.collection_id = collection_items.collection_id AND r.asset_id = collection_items.asset_id);
    DROP TABLE slot_ranks;
    """,
    # 15 Permanent codes
    """
    CREATE TABLE objects (
        object_id  TEXT PRIMARY KEY,
        kind       TEXT NOT NULL DEFAULT 'item' CHECK (kind IN ('item','group')),
        parent_id  TEXT,
        location   TEXT,
        note       TEXT,
        updated_at TEXT
    );

    CREATE TABLE withdrawn_codes (
        code         TEXT PRIMARY KEY,
        withdrawn_at TEXT NOT NULL,
        reason       TEXT NOT NULL
    );

    WITH retired(code) AS (VALUES ('C8T5'), ('J82D'), ('JYMZ'), ('6H2P'), ('G8NQ'))
    INSERT INTO withdrawn_codes (code, withdrawn_at, reason)
    SELECT code, strftime('%Y-%m-%dT%H:%M:%S', 'now'),
           'retired 4-character code from the August 2026 media-ui minter'
    FROM retired;
    """,
    # 16 Permanent code description change
    """
    CREATE TABLE code_notes (
        code       TEXT NOT NULL,
        changed_at TEXT NOT NULL,
        note       TEXT
    );
    CREATE INDEX code_notes_code ON code_notes (code, changed_at);

    INSERT INTO code_notes (code, changed_at, note)
    SELECT o.object_id, o.updated_at, o.note FROM objects o
    WHERE o.updated_at IS NOT NULL
      AND o.note IS NOT (SELECT r.note FROM reserved_ids r WHERE r.gramps_id = o.object_id);
    """,
    # 17 Permanent code links
    """
    CREATE TABLE code_instances (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        code       TEXT NOT NULL,
        kind       TEXT NOT NULL CHECK (kind IN ('url','text')),
        value      TEXT NOT NULL,
        added_at   TEXT NOT NULL,
        removed_at TEXT
    );
    CREATE INDEX code_instances_code ON code_instances (code);
    """,
    # 18 Permanent code penciling
    """
    CREATE TABLE code_pencilings (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        code        TEXT NOT NULL,
        penciled_at TEXT NOT NULL,
        crossed_at  TEXT
    );
    CREATE INDEX code_pencilings_code ON code_pencilings (code);

    INSERT INTO code_pencilings (code, penciled_at)
    SELECT gramps_id, assigned_at FROM reserved_ids
    WHERE assigned_at IS NOT NULL ORDER BY assigned_at;
    """,
    # 19 Permanent code notes
    """
    ALTER TABLE code_notes RENAME TO code_descriptions;
    DROP INDEX code_notes_code;
    CREATE INDEX code_descriptions_code ON code_descriptions (code, changed_at);

    CREATE TABLE code_notes (
        code       TEXT NOT NULL,
        changed_at TEXT NOT NULL,
        text       TEXT NOT NULL
    );
    CREATE INDEX code_notes_code ON code_notes (code, changed_at);
    """,
    # 20 GDA codes: the code that replaces a withdrawn one
    """
    ALTER TABLE withdrawn_codes ADD COLUMN successor TEXT;
    """,
    # 21 table grids over Paperless document pages
    """
    CREATE TABLE doc_tables (
        paperless_id INTEGER NOT NULL,
        page         INTEGER NOT NULL,
        title        TEXT,
        grid         TEXT NOT NULL,
        rev          INTEGER NOT NULL,
        updated_at   TEXT NOT NULL,
        PRIMARY KEY (paperless_id, page)
    );
    """,
    # 22 notes pinned to points on Paperless document pages
    """
    CREATE TABLE page_notes (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        paperless_id INTEGER NOT NULL,
        page         INTEGER NOT NULL,
        title        TEXT,
        x            REAL NOT NULL,
        y            REAL NOT NULL,
        text         TEXT NOT NULL,
        created_at   TEXT NOT NULL,
        updated_at   TEXT NOT NULL
    );
    CREATE INDEX page_notes_page ON page_notes (paperless_id, page);
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
