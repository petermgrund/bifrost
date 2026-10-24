"""Check the register against Gramps and the file services, and repair it"""

from __future__ import annotations

import sqlite3
from typing import AsyncIterator

from ..core import ids
from ..core.clients import GrampsClient, ImmichClient, PaperlessClient
from ..core.db import now
from ..core.events import SyncEvent, progress
from . import sync_immich as si

SOURCE_ATTRS = {"Immich ID": "immich", "Paperless ID": "paperless"}
DELETED_REASON = "its Gramps media was deleted (found by reconcile)"


def expected_from(media: list[dict]) -> dict[str, tuple[str | None, str | None, str]]:
    """{gramps_id: (source_system, source_id, title)} for every media the register should hold"""
    out = {}
    for m in media:
        gid = (m.get("gramps_id") or "").strip()
        if not gid:
            continue
        source = next(((system, (a.get("value") or "").strip())
                       for a in m.get("attribute_list") or []
                       for attr, system in SOURCE_ATTRS.items()
                       if a.get("type") == attr and (a.get("value") or "").strip()), None)
        if source is None and not ids.MANUAL_ID_RE.match(gid):
            continue
        system, source_id = source or (None, None)
        out[gid] = (system, source_id, m.get("desc") or "")
    return out


def _source_text(system: str | None, source_id: str | None) -> str:
    if system is None:
        return "none"
    return f"{'Immich asset' if system == 'immich' else 'Paperless document'} {source_id}"


def _item(action: str, code: str, title: str, **extra) -> SyncEvent:
    return SyncEvent(kind="item", entity="media", action=action, source_id=code, gramps_id=code,
                     title=title, **extra)


async def _gone_sources(accounts: list[ImmichClient], paperless: PaperlessClient | None,
                        sources: list[tuple[str, str, str]]) -> tuple[dict[str, str], list[str]]:
    """{code: why} for (code, system, source_id) whose Immich asset or Paperless document is
    gone, and the services that could not be asked"""
    gone: dict[str, str] = {}
    unreachable: list[str] = []
    assets = [(code, sid) for code, system, sid in sources if system == "immich"]
    if assets and accounts:
        try:
            details = await si._merged_details(accounts, list(dict.fromkeys(sid for _, sid in assets)))
        except Exception as exc:  # noqa: BLE001
            unreachable.append(f"Immich: {str(exc)[:160]}")
        else:
            for code, sid in assets:
                a = details.get(sid)
                if a is None:
                    gone[code] = f"Immich asset {sid} is gone"
                elif a.get("isTrashed"):
                    gone[code] = f"Immich asset {sid} is in the trash"
    documents = [(code, sid) for code, system, sid in sources if system == "paperless"]
    if documents and paperless is not None:
        try:
            docs = {str(i) for i in await paperless.document_ids()}
        except Exception as exc:  # noqa: BLE001
            unreachable.append(f"Paperless: {str(exc)[:160]}")
        else:
            for code, sid in documents:
                if sid not in docs:
                    gone[code] = f"Paperless document {sid} is gone"
    return gone, unreachable


async def scan(
    gramps: GrampsClient,
    paperless: PaperlessClient | None,
    accounts: list[ImmichClient],
    conn: sqlite3.Connection,
    apply: bool = False,
    selected: set[str] | None = None,
) -> AsyncIterator[SyncEvent]:
    """Rebuild what the register should say from the Gramps media attributes, diff it against
    the ledger, and with apply make the ledger agree: register media it lacks, follow a moved
    source, withdraw codes whose media is gone"""
    counts = {"registered": 0, "repointed": 0, "withdrawn": 0, "attention": 0, "errors": 0}
    try:
        media = await gramps.list_media(keys="handle,gramps_id,desc,attribute_list")
    except Exception as exc:  # noqa: BLE001
        yield SyncEvent(kind="error", detail=f"Gramps could not be read, nothing checked: {str(exc)[:200]}")
        yield SyncEvent(kind="summary", data=counts)
        return
    expected = expected_from(media)
    rows = conn.execute("SELECT * FROM minted_media").fetchall()
    ledger = {r["gramps_id"]: r for r in rows}
    yield SyncEvent(kind="started", detail=f"{len(expected)} media in Gramps, {len(rows)} codes in the ledger")

    live = [(code, system, source_id) for code, (system, source_id, _title) in sorted(expected.items())
            if system and code in ledger and not ledger[code]["withdrawn_at"]]
    total = len(expected) + len(rows) + len(live)
    done = 0

    def wanted(code: str) -> bool:
        return selected is None or f"media:{code}" in selected

    for code, (system, source_id, title) in sorted(expected.items()):
        yield progress("Checking Gramps media", done, total)
        done += 1
        r = ledger.get(code)
        if r is None:
            if apply and wanted(code):
                with conn:
                    conn.execute(
                        "INSERT INTO minted_media (gramps_id, source_system, source_id, created_at, minted_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (code, system, source_id, now(), now() if system else None))
                counts["registered"] += 1
            yield _item("created" if apply and wanted(code) else "would_create", code, title,
                        data={"cols": {"source": _source_text(system, source_id)}})
            continue
        if r["withdrawn_at"]:
            counts["attention"] += 1
            yield _item("failed", code, title,
                        detail=f"withdrawn on {r['withdrawn_at'][:10]}, but still in Gramps")
            continue
        if system and (r["source_system"], r["source_id"]) != (system, source_id):
            if apply and wanted(code):
                with conn:
                    conn.execute(
                        "UPDATE minted_media SET source_system=?, source_id=?, minted_at=COALESCE(minted_at, ?) "
                        "WHERE gramps_id=?", (system, source_id, now(), code))
                counts["repointed"] += 1
            yield _item("updated" if apply and wanted(code) else "would_update", code, title,
                        data={"cols": {"source": f"{_source_text(r['source_system'], r['source_id'])}"
                                                 f" → {_source_text(system, source_id)}"}})

    for r in rows:
        yield progress("Checking the ledger", done, total)
        done += 1
        code = r["gramps_id"]
        if code in expected or not r["source_system"] or r["withdrawn_at"]:
            continue
        if apply and wanted(code):
            with conn:
                conn.execute(
                    "UPDATE minted_media SET withdrawn_at=?, withdrawn_reason=? WHERE gramps_id=?",
                    (now(), DELETED_REASON, code))
            counts["withdrawn"] += 1
        yield _item("updated" if apply and wanted(code) else "would_update", code,
                    _source_text(r["source_system"], r["source_id"]),
                    data={"cols": {"gramps": "deleted → withdrawn"}})

    if live:
        yield progress("Checking Immich and Paperless", done, total)
    gone, unreachable = await _gone_sources(accounts, paperless, live)
    done += len(live)
    for why in unreachable:
        counts["errors"] += 1
        yield SyncEvent(kind="error", detail=f"{why}; its records were not checked")
    for code, why in sorted(gone.items()):
        counts["attention"] += 1
        yield _item("failed", code, expected.get(code, (None, None, ""))[2] or code, detail=why)
    if total:
        yield progress("Checking Immich and Paperless", done, total)
    yield SyncEvent(kind="summary", data=counts)
