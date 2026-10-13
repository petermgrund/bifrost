"""Record types Bifrost holds: edits laid over the shipped ones, new ones of Peter's own, every saved version kept"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone

KINDS = ("override", "custom", "shipped")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")
MAX_DEFINITION = 200_000


class RecordTypeError(Exception):
    """A refused change, with the HTTP status that fits it"""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row(r: sqlite3.Row) -> dict:
    return {"id": r["id"], "kind": r["kind"], "definition": json.loads(r["definition"]) if r["definition"] else None,
            "version": r["version"], "deleted": bool(r["deleted"]), "saved_at": r["saved_at"]}


def list_types(conn: sqlite3.Connection) -> list[dict]:
    """Every record type with a saved change, deleted ones included"""
    return [_row(r) for r in conn.execute("SELECT * FROM record_types ORDER BY id")]


def get_type(conn: sqlite3.Connection, type_id: str) -> dict | None:
    r = conn.execute("SELECT * FROM record_types WHERE id=?", (type_id,)).fetchone()
    return _row(r) if r else None


def _write(conn: sqlite3.Connection, type_id: str, kind: str, definition: dict | None, deleted: bool) -> dict:
    if not ID_RE.match(type_id or ""):
        raise RecordTypeError(400, "A record type id is lower-case letters, digits and hyphens")
    if kind not in KINDS:
        raise RecordTypeError(400, f"Unknown kind {kind!r}")
    text = json.dumps(definition, ensure_ascii=False) if definition is not None else None
    if text and len(text) > MAX_DEFINITION:
        raise RecordTypeError(413, "The record type is too large")
    current = get_type(conn, type_id)
    version = (current["version"] if current else 0) + 1
    stamp = _now()
    with conn:
        conn.execute("INSERT OR REPLACE INTO record_types (id, kind, definition, version, deleted, saved_at) VALUES (?, ?, ?, ?, ?, ?)",
                     (type_id, kind, text, version, int(deleted), stamp))
        conn.execute("INSERT INTO record_type_versions (id, version, kind, definition, deleted, saved_at) VALUES (?, ?, ?, ?, ?, ?)",
                     (type_id, version, kind, text, int(deleted), stamp))
    return get_type(conn, type_id)


def save(conn: sqlite3.Connection, type_id: str, kind: str, definition: dict) -> dict:
    """Save a record type's definition as its next version"""
    if kind == "shipped" or not isinstance(definition, dict):
        raise RecordTypeError(400, "Save an override or a custom record type with its definition")
    if not str(definition.get("name") or "").strip():
        raise RecordTypeError(400, "The record type needs a name")
    return _write(conn, type_id, kind, definition, False)


def restore(conn: sqlite3.Connection, type_id: str) -> dict:
    """Bring a built-in record type back as it ships, as its next version"""
    current = get_type(conn, type_id)
    if current and current["kind"] == "custom":
        raise RecordTypeError(400, "A record type of your own has nothing to restore")
    return _write(conn, type_id, "shipped", None, False)


def delete(conn: sqlite3.Connection, type_id: str, kind: str) -> dict:
    """Take a record type out of the wizard, keeping its versions"""
    current = get_type(conn, type_id)
    keep_kind = current["kind"] if current else kind
    return _write(conn, type_id, keep_kind, current["definition"] if current else None, True)


def general_drafts(conn: sqlite3.Connection, limit: int = 100) -> list[dict]:
    """The wizard drafts of General form citations, newest first, to start a record type from"""
    rows = conn.execute("SELECT citation_handle, draft, created_at FROM citation_drafts WHERE record_type='general' "
                        "ORDER BY created_at DESC LIMIT ?", (limit,))
    return [{"handle": r["citation_handle"], "draft": json.loads(r["draft"]), "created_at": r["created_at"]} for r in rows]


def versions(conn: sqlite3.Connection, type_id: str) -> list[dict]:
    """Every saved version of a record type, oldest first"""
    return [_row(r) for r in conn.execute(
        "SELECT * FROM record_type_versions WHERE id=? ORDER BY version", (type_id,))]
