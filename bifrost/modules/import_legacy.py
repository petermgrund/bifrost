"""One-shot import of the scattered legacy state files into Bifrost's SQLite.

Idempotent: re-running upserts. The legacy files are left untouched — they
remain the live state for the legacy pipeline until each module cuts over
(faces keeps a write-through YAML export until Phase 2; see DESIGN.md §7).
"""

from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

LEGACY = {
    "person_map": Path("/opt/stacks/immich-to-gramps/person_map.yaml"),
    "minted_immich": Path("/opt/stacks/immich-to-gramps/minted.csv"),
    "minted_paperless": Path("/opt/stacks/paper-to-gramps/minted.csv"),
    "versions": Path("/opt/stacks/paper-to-gramps/versions.json"),
    "transcriptions": Path("/opt/stacks/paper-to-gramps/transcriptions.json"),
}


@dataclass
class ImportResult:
    counts: dict[str, int]
    missing: list[str]


def import_all(conn: sqlite3.Connection, paths: dict[str, Path] = LEGACY) -> ImportResult:
    now = datetime.now().isoformat(timespec="seconds")
    counts: dict[str, int] = {}
    missing: list[str] = []

    def have(key: str) -> bool:
        if paths[key].is_file():
            return True
        missing.append(f"{key}: {paths[key]}")
        return False

    with conn:
        if have("person_map"):
            entries = (yaml.safe_load(paths["person_map"].read_text()) or {}).get("people") or []
            for e in entries:
                conn.execute(
                    """INSERT INTO person_links (gramps_handle, immich_person_id, label, created_at)
                       VALUES (?, ?, ?, ?)
                       ON CONFLICT (gramps_handle, immich_person_id)
                       DO UPDATE SET label = excluded.label""",
                    (e["gramps_handle"], e["immich_person_id"], e.get("label"), now),
                )
            counts["person_links"] = len(entries)

        for key, system in (("minted_immich", "immich"), ("minted_paperless", "paperless")):
            if not have(key):
                continue
            n = 0
            with paths[key].open(newline="") as fh:
                for row in csv.DictReader(fh):
                    source_id = row.get("immich_id") or row.get("paperless_id")
                    conn.execute(
                        """INSERT OR REPLACE INTO minted_media
                           (gramps_id, source_system, source_id, title, minted_at)
                           VALUES (?, ?, ?, ?, ?)""",
                        (row["gramps_id"], system, source_id, row.get("title"), row["minted_at"]),
                    )
                    n += 1
            counts[f"minted_media ({system})"] = n

        if have("versions"):
            data = json.loads(paths["versions"].read_text())
            for pid, v in data.items():
                conn.execute(
                    """INSERT OR REPLACE INTO doc_versions
                       (paperless_id, checksum, gramps_id, updated_at)
                       VALUES (?, ?, ?, ?)""",
                    (int(pid), v["checksum"], v.get("gramps_id"), now),
                )
            counts["doc_versions"] = len(data)

        if have("transcriptions"):
            data = json.loads(paths["transcriptions"].read_text())
            for pid, t in data.items():
                conn.execute(
                    """INSERT OR REPLACE INTO transcription_state
                       (paperless_id, content_hash, note_handle, gramps_note_id,
                        gramps_media_id, translation_handle, translation_note_id, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        int(pid),
                        t["content_hash"],
                        t.get("note_handle"),
                        t.get("gramps_note_id"),
                        t.get("gramps_media_id"),
                        t.get("translation_handle"),
                        t.get("translation_note_id"),
                        now,
                    ),
                )
            counts["transcription_state"] = len(data)

    return ImportResult(counts=counts, missing=missing)
