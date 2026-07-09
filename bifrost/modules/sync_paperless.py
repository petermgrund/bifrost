from __future__ import annotations

import hashlib
import logging
import mimetypes
import sqlite3
from datetime import datetime
from typing import AsyncIterator

from ..core.clients import GrampsClient, PaperlessClient
from ..core.config import SyncPaperlessConfig
from ..core.events import SyncEvent
from ..core.ids import generate_gramps_id, generate_handle
from .citations import next_sequential_id

log = logging.getLogger("bifrost.sync.paperless")

QUAL_EXACT = "Exact"
QUAL_CIRCA = "Circa"
QUAL_BEFORE = "Before"
QUAL_AFTER = "After"
QUAL_YEAR = "Year only"
QUAL_DECADE = "Decade only"
# QUAL_TO_FROM = "To/from"

MOD_REGULAR, MOD_BEFORE, MOD_AFTER, MOD_ABOUT = 0, 1, 2, 3
QUAL_REGULAR_Q, QUAL_ESTIMATED_Q = 0, 1

SKIP_TITLE_SYNC_TAG = "skip-title-sync"
TRANSLATION_DELIMITER = "======== ENGLISH TRANSLATION ========"

BACKLINK_OBJ_TYPES = {
    "person": "people",
    "family": "families",
    "event": "events",
    "citation": "citations",
    "source": "sources",
    "place": "places",
}


# ---------------------------------------------------------------------------
# Pure helpers 
# ---------------------------------------------------------------------------

def build_gramps_date_from_paperless(doc: dict, qualifier_label: str | None) -> dict | None:
    if not qualifier_label:
        return None
    created = doc.get("created") or doc.get("created_date")
    if not created:
        return None
    try:
        dt = datetime.fromisoformat(str(created))
    except (ValueError, TypeError):
        return None

    # if qualifier_label == QUAL_TO_FROM:
    #     log.warning("Paperless #%d date qualifier has no Gramps equivalent",
    #                 doc.get("id", 0))
    #     return None

    day, month, year = dt.day, dt.month, dt.year
    modifier, quality = MOD_REGULAR, QUAL_REGULAR_Q

    if qualifier_label == QUAL_EXACT:
        pass
    elif qualifier_label == QUAL_CIRCA:
        modifier = MOD_ABOUT
    elif qualifier_label == QUAL_BEFORE:
        modifier = MOD_BEFORE
    elif qualifier_label == QUAL_AFTER:
        modifier = MOD_AFTER
    elif qualifier_label == QUAL_YEAR:
        day, month = 0, 0
    elif qualifier_label == QUAL_DECADE:
        day, month = 0, 0
        year = (year // 10) * 10
        quality = QUAL_ESTIMATED_Q
    else:
        log.warning("Paperless #%d unknown date qualifier %r",
                    doc.get("id", 0), qualifier_label)
        return None

    return {
        "_class": "Date",
        "dateval": [day, month, year, False],
        "modifier": modifier,
        "quality": quality,
        "text": "",
    }


def dates_equal(a: dict | None, b: dict | None) -> bool:
    if not a and not b:
        return True
    if not a or not b:
        return False
    return ((a.get("dateval") or []) == (b.get("dateval") or [])
            and a.get("modifier", 0) == b.get("modifier", 0)
            and a.get("quality", 0) == b.get("quality", 0))


def format_gramps_date(date_obj: dict | None) -> str:
    if not date_obj:
        return "(none)"
    dv = date_obj.get("dateval") or []
    if len(dv) < 3:
        return "(none)"
    day, month, year = dv[0], dv[1], dv[2]
    if year == 0 and month == 0 and day == 0:
        return "(none)"
    if day == 0 and month == 0:
        date_str = f"{year}"
    elif day == 0:
        date_str = f"{year}-{month:02d}"
    else:
        date_str = f"{year}-{month:02d}-{day:02d}"
    mod = {1: "Before ", 2: "After ", 3: "About "}.get(date_obj.get("modifier", 0), "")
    qual = {1: "Est. ", 2: "Calc. "}.get(date_obj.get("quality", 0), "")
    return f"{qual}{mod}{date_str}"


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def split_transcription(content: str) -> tuple[str, str | None]:
    if TRANSLATION_DELIMITER in content:
        parts = content.split(TRANSLATION_DELIMITER, 1)
        return parts[0].strip(), (parts[1].strip() or None)
    return content, None


def build_note_obj(handle: str, gramps_id: str, text: str, note_type: str) -> dict:
    return {
        "_class": "Note",
        "handle": handle,
        "gramps_id": gramps_id,
        "text": {"_class": "StyledText", "string": text, "tags": []},
        "type": note_type,
        "format": 0,
        "change": int(datetime.utcnow().timestamp()),
        "tag_list": [],
        "private": False,
    }

# DB 

def _get_version(conn: sqlite3.Connection, doc_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM doc_versions WHERE paperless_id=?", (doc_id,)
    ).fetchone()


def _set_version(conn: sqlite3.Connection, doc_id: int, checksum: str, gramps_id: str) -> None:
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO doc_versions"
            " (paperless_id, checksum, gramps_id, updated_at) VALUES (?, ?, ?, ?)",
            (doc_id, checksum, gramps_id, datetime.now().isoformat(timespec="seconds")),
        )


def _get_tx(conn: sqlite3.Connection, doc_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM transcription_state WHERE paperless_id=?", (doc_id,)
    ).fetchone()


def _set_tx(conn: sqlite3.Connection, doc_id: int, **fields) -> None:
    row = _get_tx(conn, doc_id)
    current = dict(row) if row else {"paperless_id": doc_id}
    current.update(fields)
    current["updated_at"] = datetime.now().isoformat(timespec="seconds")
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO transcription_state"
            " (paperless_id, content_hash, note_handle, gramps_note_id,"
            "  gramps_media_id, translation_handle, translation_note_id, updated_at)"
            " VALUES (:paperless_id, :content_hash, :note_handle, :gramps_note_id,"
            "  :gramps_media_id, :translation_handle, :translation_note_id, :updated_at)",
            {"content_hash": None, "note_handle": None, "gramps_note_id": None,
             "gramps_media_id": None, "translation_handle": None,
             "translation_note_id": None, **current},
        )

# sync generator

def _doc_gramps_id(doc: dict, field_id: int) -> str | None:
    for cf in doc.get("custom_fields", []):
        if cf["field"] == field_id:
            val = cf.get("value")
            if val and str(val).strip():
                return str(val).strip()
    return None


async def paperless_id_for_media(gramps: GrampsClient, media_gramps_id: str) -> int | None:
    media = await gramps.get_media_by_gramps_id(media_gramps_id.strip())
    if not media:
        return None
    for attr in media.get("attribute_list", []):
        if attr.get("type") == "Paperless ID":
            try:
                return int(attr["value"])
            except (ValueError, TypeError, KeyError):
                return None
    return None


async def sync(
    paperless: PaperlessClient,
    gramps: GrampsClient,
    conn: sqlite3.Connection,
    cfg: SyncPaperlessConfig,
    apply: bool,
    force_transcriptions: bool = False,
    transcriptions_only: bool = False,
    single_doc_id: int | None = None,
    versions_only: bool = False,
    selected: set[str] | None = None,
) -> AsyncIterator[SyncEvent]:
    counts = {"created": 0, "skipped": 0, "versions_updated": 0, "baselined": 0,
              "titles_updated": 0, "dates_updated": 0,
              "tx_created": 0, "tx_updated": 0, "tx_skipped": 0, "errors": 0}

    existing_ids = await gramps.list_media_gramps_ids()

    q_options: dict[str, str] = {}
    q_field = cfg.date_qualifier_field_id
    if q_field and not transcriptions_only:
        try:
            q_options = await paperless.resolve_custom_field_options(q_field)
        except Exception as exc:  # noqa BLE001
            yield SyncEvent(kind="error", detail=f"date qualifier field options: {exc}")
            q_field = None

    def _prospective_cols(doc: dict) -> dict:
        cols: dict = {}
        if q_field:
            q_val = paperless.get_custom_field_value(doc, q_field)
            date_obj = build_gramps_date_from_paperless(
                doc, q_options.get(q_val) if q_val else None)
            if date_obj:
                cols["date"] = "new"
        if cfg.transcription_tag_id and cfg.transcription_tag_id in doc.get("tags", []):
            content = (doc.get("content") or "").strip()
            if content:
                _tx, tl = split_transcription(content)
                tracked = _get_tx(conn, doc["id"])
                cols["transcription"] = ("modified" if tracked and tracked["note_handle"]
                                         else "new")
                if tl:
                    cols["translation"] = ("modified" if tracked and tracked["translation_handle"]
                                           else "new")
            else:
                cols["transcription"] = "tagged, no text yet"
        return cols

    documents: list[dict] = []
    tag_map: dict[str, int] = {}
    if not transcriptions_only:
        for name in cfg.sync_tags:
            tid = await paperless.resolve_tag_id(name)
            if tid is not None:
                tag_map[name] = tid
        if not tag_map:
            yield SyncEvent(kind="error", detail="no sync tags found in Paperless")
            yield SyncEvent(kind="summary", data=counts)
            return
        documents = await paperless.list_documents_by_tags(list(tag_map.values()))
        if single_doc_id is not None:
            documents = [d for d in documents if d["id"] == single_doc_id]
        yield SyncEvent(kind="started",
                        detail=f"{len(documents)} tagged document(s) in Paperless")

    if versions_only:
        bands = ["versions"]
    elif transcriptions_only:
        bands = ["tx"]
    else:
        bands = ["media", "versions", "details"] + (["tx"] if cfg.transcription_tag_id else [])

    def _progress(band: str, label: str = "", done: int = 0, total: int = 0) -> SyncEvent:
        frac = (bands.index(band) + (done / total if total else 0)) / len(bands)
        return SyncEvent(kind="progress", detail=label,
                         data={"done": done, "total": total,
                               "percent": round(100 * frac)})

    # Phase 1 media sync
    n_docs = len(documents)
    for i, doc in enumerate(documents if not versions_only else []):
        yield _progress("media", "Checking new documents", i, n_docs)
        doc_id = doc["id"]
        title = doc.get("title", f"Untitled (Paperless #{doc_id})")
        if _doc_gramps_id(doc, cfg.gramps_id_field_id):
            counts["skipped"] += 1
            continue
        if selected is not None and f"doc:{doc_id}" not in selected:
            continue

        try:
            metadata = await paperless.get_document_metadata(doc_id)
        except Exception as exc:  # noqa BLE001
            counts["errors"] += 1
            yield SyncEvent(kind="item", entity="doc", action="failed",
                            source_id=str(doc_id), title=title,
                            detail=f"metadata fetch failed: {exc}")
            continue
        gramps_path = f"paperless/{metadata['media_filename']}"

        if not apply:
            counts["created"] += 1
            yield SyncEvent(kind="item", entity="doc", action="would_create",
                            source_id=str(doc_id), title=title,
                            data={"path": gramps_path, "cols": _prospective_cols(doc)})
            continue

        gramps_id = generate_gramps_id(existing_ids)
        handle = generate_handle()
        media_obj = {
            "_class": "Media",
            "handle": handle,
            "gramps_id": gramps_id,
            "desc": title,
            "path": gramps_path,
            "mime": doc.get("mime_type", "application/octet-stream"),
            "private": False,
            "change": int(datetime.utcnow().timestamp()),
            "attribute_list": [
                {"_class": "Attribute", "type": "Paperless URL",
                 "value": f"{cfg.public_url}/documents/{doc_id}/details",
                 "private": False, "citation_list": [], "note_list": []},
                {"_class": "Attribute", "type": "Paperless ID", "value": str(doc_id),
                 "private": False, "citation_list": [], "note_list": []},
            ],
        }

        try:
            await gramps.create_media(media_obj)
        except Exception as exc:  # noqa BLE001
            counts["errors"] += 1
            yield SyncEvent(kind="item", entity="doc", action="failed",
                            source_id=str(doc_id), title=title, detail=str(exc))
            continue

        try:
            cfs = list(doc.get("custom_fields", []))
            updates = {
                cfg.gramps_id_field_id: gramps_id,
                cfg.gramps_url_field_id: f"{cfg.gramps_public_url}/media/{gramps_id}",
            }
            seen: set[int] = set()
            for cf in cfs:
                if cf["field"] in updates:
                    cf["value"] = updates[cf["field"]]
                    seen.add(cf["field"])
            for fid, value in updates.items():
                if fid not in seen:
                    cfs.append({"field": fid, "value": value})
            await paperless.patch_custom_fields(doc_id, cfs)
            doc["custom_fields"] = cfs  # later phases must see it as synced
        except Exception as exc:  # noqa BLE001
            yield SyncEvent(
                kind="error", source_id=str(doc_id),
                detail=(f"media {gramps_id} created in Gramps but gramps_id "
                        f"write-back to Paperless FAILED. Next run would "
                        f"duplicate this doc. You must fix the custom field manually. ({exc})"),
            )

        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO minted_media"
                " (gramps_id, source_system, source_id, title, minted_at)"
                " VALUES (?, 'paperless', ?, ?, ?)",
                (gramps_id, str(doc_id), title,
                 datetime.now().isoformat(timespec="seconds")),
            )
        counts["created"] += 1
        yield SyncEvent(kind="item", entity="doc", action="created",
                        source_id=str(doc_id), gramps_id=gramps_id, title=title,
                        data={"path": gramps_path, "cols": _prospective_cols(doc)})

    # Phase 2 version sync
    img_tag_id = tag_map.get("img")
    for i, doc in enumerate(documents):
        yield _progress("versions", "Checking versions", i, n_docs)
        doc_id = doc["id"]
        title = doc.get("title", f"Untitled (Paperless #{doc_id})")
        gramps_id = _doc_gramps_id(doc, cfg.gramps_id_field_id)
        if not gramps_id:
            continue
        if selected is not None and f"doc:{doc_id}" not in selected:
            continue
        try:
            metadata = await paperless.get_document_metadata(doc_id)
        except Exception as exc:  # noqa BLE001
            counts["errors"] += 1
            yield SyncEvent(kind="item", entity="doc", action="failed",
                            source_id=str(doc_id), title=title,
                            detail=f"version check failed: {exc}")
            continue
        current_checksum = metadata.get("original_checksum", "")

        tracked = _get_version(conn, doc_id)
        if tracked is None:
            if apply:
                _set_version(conn, doc_id, current_checksum, gramps_id)
            counts["baselined"] += 1
            continue
        if current_checksum == tracked["checksum"]:
            continue

        #version changed
        new_path = f"paperless/{metadata['media_filename']}"
        guessed, _ = mimetypes.guess_type(metadata["media_filename"])
        new_mime = guessed or doc.get("mime_type", "application/octet-stream")
        media = await gramps.get_media_by_gramps_id(gramps_id)
        if not media:
            counts["errors"] += 1
            yield SyncEvent(kind="item", entity="doc", action="failed",
                            source_id=str(doc_id), title=title,
                            detail=f"no Gramps media {gramps_id}")
            continue

        vcols: dict = {"version": "changed"}
        if media.get("path") != new_path or media.get("mime") != new_mime:
            vcols["path/mime"] = "updated"
            if apply:
                media["path"] = new_path
                media["mime"] = new_mime
                media["change"] = int(datetime.utcnow().timestamp())
                await gramps.update_media(media["handle"], media)

        has_img_tag = img_tag_id and img_tag_id in doc.get("tags", [])
        if has_img_tag:
            cleared = 0
            backlinks = await gramps.get_media_backlinks(media["handle"])
            for bl_type, api_path in BACKLINK_OBJ_TYPES.items():
                for obj_handle in backlinks.get(bl_type, []):
                    obj = await gramps.get_object(api_path, obj_handle)
                    modified = False
                    for mref in obj.get("media_list", []):
                        if mref.get("ref") == media["handle"] and mref.get("rect"):
                            cleared += 1
                            if apply:
                                mref["rect"] = None
                                modified = True
                    if modified:
                        await gramps.update_object(api_path, obj_handle, obj)
            if cleared:
                vcols["face rects"] = f"{cleared} cleared"

        if apply:
            _set_version(conn, doc_id, current_checksum, gramps_id)
        counts["versions_updated"] += 1
        yield SyncEvent(kind="item", entity="doc",
                        action="updated" if apply else "would_update",
                        source_id=str(doc_id), gramps_id=gramps_id, title=title,
                        data={"cols": vcols})

    # Phase 3 date/title sync
    skip_tag_handle = None
    if documents and not versions_only:
        try:
            skip_tag_handle = await gramps.get_tag_handle(SKIP_TITLE_SYNC_TAG)
        except Exception:  # noqa BLE001
            skip_tag_handle = None

    for i, doc in enumerate(documents if not versions_only else []):
        yield _progress("details", "Checking titles and dates", i, n_docs)
        doc_id = doc["id"]
        title = doc.get("title", f"Untitled (Paperless #{doc_id})")
        gramps_id = _doc_gramps_id(doc, cfg.gramps_id_field_id)
        if not gramps_id:
            continue
        # doc:{id} selected = the doc was just created; apply its date/title now
        if selected is not None and not ({f"media:{doc_id}", f"doc:{doc_id}"} & selected):
            continue
        try:
            media = await gramps.get_media_by_gramps_id(gramps_id)
        except Exception as exc:  # noqa BLE001
            counts["errors"] += 1
            yield SyncEvent(kind="item", entity="doc", action="failed",
                            source_id=str(doc_id), title=title, detail=str(exc))
            continue
        if not media:
            continue

        media_dirty = False
        mcols: dict = {}

        # Title sync but ignore skip-title-sync Gramps tagged assets
        skip_title = bool(skip_tag_handle and skip_tag_handle in (media.get("tag_list") or []))
        if not skip_title and media.get("desc") != title:
            mcols["title"] = f"{media.get('desc')!r} → {title!r}"
            if apply:
                media["desc"] = title
                media_dirty = True
            counts["titles_updated"] += 1

        q_label = None
        if q_field:
            q_val = paperless.get_custom_field_value(doc, q_field)
            q_label = q_options.get(q_val) if q_val else None

        date_obj = build_gramps_date_from_paperless(doc, q_label)
        if date_obj is not None and not dates_equal(media.get("date") or {}, date_obj):
            mcols["date"] = ("changed" if format_gramps_date(media.get("date")) != "(none)"
                             else "new")
            if apply:
                media["date"] = date_obj
                media_dirty = True
            counts["dates_updated"] += 1

        if media_dirty:
            try:
                media["change"] = int(datetime.utcnow().timestamp())
                await gramps.update_media(media["handle"], media)
            except Exception as exc:  # noqa BLE001
                counts["errors"] += 1
                yield SyncEvent(kind="item", entity="doc", action="failed",
                                source_id=str(doc_id), title=title, detail=str(exc))
                continue
        if mcols:
            yield SyncEvent(kind="item", entity="media",
                            action="updated" if apply else "would_update",
                            source_id=str(doc_id), gramps_id=gramps_id, title=title,
                            data={"cols": mcols})

    # phase 4 transcriptions
    if cfg.transcription_tag_id and not versions_only:
        tx_docs = await paperless.list_documents_by_tag(cfg.transcription_tag_id)
        if single_doc_id is not None:
            tx_docs = [d for d in tx_docs if d["id"] == single_doc_id]
            detail = (f"document #{single_doc_id} (transcription-tagged)"
                      if tx_docs
                      else f"document #{single_doc_id} is not transcription-tagged "
                           "— nothing to resync")
            yield SyncEvent(kind="started", detail=detail)
        else:
            yield SyncEvent(kind="started",
                            detail=f"{len(tx_docs)} document(s) with transcription tag")
        note_ids: set[str] | None = None
        for i, doc in enumerate(tx_docs):
            yield _progress("tx", "Checking transcriptions", i, len(tx_docs))
            doc_id = doc["id"]
            if selected is not None and not ({f"note:{doc_id}", f"doc:{doc_id}"} & selected):
                continue
            title = doc.get("title", f"Untitled (Paperless #{doc_id})")
            gramps_id = _doc_gramps_id(doc, cfg.gramps_id_field_id)
            if not gramps_id:
                counts["tx_skipped"] += 1
                continue
            content = (doc.get("content") or "").strip()
            if not content:
                counts["tx_skipped"] += 1
                continue
            c_hash = content_hash(content)
            tracked = _get_tx(conn, doc_id)
            if not force_transcriptions and tracked and tracked["content_hash"] == c_hash:
                counts["tx_skipped"] += 1
                continue

            is_update = tracked is not None and tracked["note_handle"]
            tx_text, tl_text = split_transcription(content)
            has_translation = tl_text is not None
            had_translation = bool(tracked["translation_handle"]) if tracked else False

            ncols: dict = {"transcription": "modified" if is_update else "new"}
            if has_translation:
                ncols["translation"] = "modified" if had_translation else "new"
            elif had_translation:
                ncols["translation"] = "removed"

            if not apply:
                counts["tx_updated" if is_update else "tx_created"] += 1
                yield SyncEvent(kind="item", entity="note",
                                action="would_update" if is_update else "would_create",
                                source_id=str(doc_id), gramps_id=gramps_id,
                                title=title, data={"cols": ncols})
                continue

            try:
                media = await gramps.get_media_by_gramps_id(gramps_id)
                if not media:
                    # creating a note would orphan it
                    counts["errors"] += 1
                    yield SyncEvent(
                        kind="item", entity="note", action="failed",
                        source_id=str(doc_id), title=title,
                        detail=(f"Gramps media {gramps_id} no longer exists!"))
                    continue

                async def mint_note_id() -> str:
                    nonlocal note_ids
                    if note_ids is None:
                        items = await gramps._paged("/notes/", keys="gramps_id")
                        note_ids = {i["gramps_id"] for i in items if i.get("gramps_id")}
                    nid = next_sequential_id("N", note_ids)
                    note_ids.add(nid)
                    return nid

                if is_update:
                    note_handle = tracked["note_handle"]
                    await gramps.update_note(
                        note_handle,
                        build_note_obj(note_handle, tracked["gramps_note_id"],
                                       tx_text, "Transcription"),
                    )
                    updates: dict = {"content_hash": c_hash}
                    if has_translation and had_translation:
                        await gramps.update_note(
                            tracked["translation_handle"],
                            build_note_obj(tracked["translation_handle"],
                                           tracked["translation_note_id"],
                                           tl_text, "Translation"),
                        )
                    elif has_translation and not had_translation:
                        tl_handle = generate_handle()
                        tl_gid = await mint_note_id()
                        await gramps.create_note(
                            build_note_obj(tl_handle, tl_gid, tl_text, "Translation"))
                        notes = media.get("note_list", [])
                        if tl_handle not in notes:
                            notes.append(tl_handle)
                            media["note_list"] = notes
                            await gramps.update_media(media["handle"], media)
                        updates["translation_handle"] = tl_handle
                        updates["translation_note_id"] = tl_gid
                    _set_tx(conn, doc_id, **updates)
                    counts["tx_updated"] += 1
                else:
                    note_handle = generate_handle()
                    note_gid = await mint_note_id()
                    await gramps.create_note(
                        build_note_obj(note_handle, note_gid, tx_text, "Transcription"))
                    new_handles = [note_handle]
                    fields = {"note_handle": note_handle, "gramps_note_id": note_gid,
                              "content_hash": c_hash, "gramps_media_id": gramps_id}
                    if has_translation:
                        tl_handle = generate_handle()
                        tl_gid = await mint_note_id()
                        await gramps.create_note(
                            build_note_obj(tl_handle, tl_gid, tl_text, "Translation"))
                        new_handles.append(tl_handle)
                        fields["translation_handle"] = tl_handle
                        fields["translation_note_id"] = tl_gid
                    notes = media.get("note_list", [])
                    for h in new_handles:
                        if h not in notes:
                            notes.append(h)
                    media["note_list"] = notes
                    await gramps.update_media(media["handle"], media)
                    _set_tx(conn, doc_id, **fields)
                    counts["tx_created"] += 1

                yield SyncEvent(kind="item", entity="note",
                                action="updated" if is_update else "created",
                                source_id=str(doc_id), gramps_id=gramps_id,
                                title=title, data={"cols": ncols})
            except Exception as exc:  # noqa BLE001
                counts["errors"] += 1
                yield SyncEvent(kind="item", entity="note", action="failed",
                                source_id=str(doc_id), title=title, detail=str(exc))

    yield SyncEvent(kind="summary", data=counts)
