"""Paperless documents to Gramps media"""

from __future__ import annotations

import logging
import mimetypes
from dataclasses import replace
from datetime import datetime, timezone
from typing import AsyncIterator, Iterable

from ..core import ids
from ..core.clients import GrampsClient, PaperlessClient, PaperlessError
from ..core.clients.gramps import note_obj as build_note_obj
from ..core.config import SyncPaperlessConfig
from ..core.dates import MODIFIERS, QUALITIES, dates_equal, format_gramps_date, plain_date
from ..core.events import SyncEvent, progress
from . import codes

log = logging.getLogger("bifrost.sync.paperless")

QUAL_EXACT = "Exact"
QUAL_CIRCA = "Circa"
QUAL_BEFORE = "Before"
QUAL_AFTER = "After"
QUAL_YEAR = "Year only"
QUAL_DECADE = "Decade only"

TX_NOTE, TL_NOTE = "Transcription", "Translation"

BACKLINK_OBJ_TYPES = {
    "person": "people",
    "family": "families",
    "event": "events",
    "citation": "citations",
    "source": "sources",
    "place": "places",
}


def build_gramps_date(doc: dict, qualifier_label: str | None) -> dict | None:
    """The Paperless created date as a Gramps Date, shaped by the date qualifier field"""
    if not qualifier_label:
        return None
    created = doc.get("created") or doc.get("created_date")
    if not created:
        return None
    try:
        dt = datetime.fromisoformat(str(created))
    except (ValueError, TypeError):
        return None

    day, month, year = dt.day, dt.month, dt.year
    modifier, quality = MODIFIERS["regular"], QUALITIES["regular"]

    if qualifier_label == QUAL_EXACT:
        pass
    elif qualifier_label == QUAL_CIRCA:
        modifier = MODIFIERS["about"]
    elif qualifier_label == QUAL_BEFORE:
        modifier = MODIFIERS["before"]
    elif qualifier_label == QUAL_AFTER:
        modifier = MODIFIERS["after"]
    elif qualifier_label == QUAL_YEAR:
        day, month = 0, 0
    elif qualifier_label == QUAL_DECADE:
        day, month = 0, 0
        year = (year // 10) * 10
        quality = QUALITIES["estimated"]
    else:
        log.warning("Paperless #%d unknown date qualifier %r",
                    doc.get("id", 0), qualifier_label)
        return None

    return plain_date(day, month, year, modifier, quality)


def split_transcription(content: str, marker: str) -> tuple[str, str | None]:
    """(transcription, translation): the translation is what follows the marker line"""
    if marker in content:
        parts = content.split(marker, 1)
        return parts[0].strip(), (parts[1].strip() or None)
    return content, None


def _doc_gramps_id(doc: dict, field_id: int) -> str | None:
    for cf in doc.get("custom_fields", []):
        if cf["field"] == field_id:
            val = cf.get("value")
            if val and str(val).strip():
                return str(val).strip()
    return None


def _attr(attr_type: str, value: str) -> dict:
    return {"_class": "Attribute", "type": attr_type, "value": value,
            "private": False, "citation_list": [], "note_list": []}


def attribute_value(raw, options: dict | None = None) -> str | None:
    """A custom field's value as attribute text: a select option becomes its label,
    a list joins its members, and nothing at all is None"""
    if raw is None or raw == "" or raw == []:
        return None
    if isinstance(raw, bool):
        return "Yes" if raw else "No"
    if isinstance(raw, list):
        parts = [attribute_value(v, options) for v in raw]
        return ", ".join(p for p in parts if p) or None
    text = str(raw).strip()
    if not text:
        return None
    for key in (raw, text):
        try:
            if options and key in options:
                return str(options[key])
        except TypeError:
            pass
    return text


def attribute_changes(media: dict, wanted: dict[str, str | None]) -> dict[str, str]:
    """What mirror_attributes would do to the media: attribute name -> new, changed or removed"""
    attrs = media.get("attribute_list") or []
    cols: dict[str, str] = {}
    for name, value in wanted.items():
        current = [a.get("value") for a in attrs if a.get("type") == name]
        if value is None:
            if current:
                cols[name] = "removed"
        elif current != [value]:
            cols[name] = "changed" if current else "new"
    return cols


def mirror_attributes(media: dict, wanted: dict[str, str | None]) -> dict[str, str]:
    """Make the media carry one attribute per wanted name with the wanted value (None removes it),
    in place where it already was; other attributes are not touched. Returns what changed"""
    cols = attribute_changes(media, wanted)
    if not cols:
        return cols
    out: list[dict] = []
    placed: set[str] = set()
    for a in media.get("attribute_list") or []:
        name = a.get("type")
        if name not in cols:
            out.append(a)
        elif wanted[name] is not None and name not in placed:
            out.append(_attr(name, wanted[name]))
            placed.add(name)
    out += [_attr(name, wanted[name]) for name in cols
            if wanted[name] is not None and name not in placed]
    media["attribute_list"] = out
    return cols


def _media_mime(metadata: dict, doc: dict) -> str:
    """MIME of the file the media points at, the latest version; Paperless's
    doc mime_type describes the original, which a new version may not match"""
    guessed, _ = mimetypes.guess_type(metadata["media_filename"])
    return guessed or doc.get("mime_type", "application/octet-stream")


def _text(note: dict | None) -> str:
    return ((note or {}).get("text") or {}).get("string") or ""


def _note_of(notes: list[dict], kind: str) -> dict | None:
    return next((n for n in notes if n.get("type") == kind), None)


def _stamp(media: dict) -> None:
    media["change"] = int(datetime.now(timezone.utc).timestamp())


class NamesError(Exception):
    pass


async def resolve_names(paperless: PaperlessClient, cfg: SyncPaperlessConfig) -> SyncPaperlessConfig:
    """The config with every custom field and tag written as a name replaced by its Paperless id"""
    fields = [cfg.gramps_id_field_id, cfg.gramps_url_field_id, cfg.date_qualifier_field_id,
              *(f for f, _ in cfg.attribute_fields)]
    if not any(isinstance(v, str) for v in (*fields, cfg.transcription_tag_id)):
        return cfg
    by_kind: dict[str, dict[str, int]] = {}
    missing: list[str] = []

    async def ident(kind: str, label: str, value):
        if not isinstance(value, str):
            return value
        if kind not in by_kind:
            by_kind[kind] = await paperless.names(kind)
        found = by_kind[kind].get(value.casefold())
        if found is None:
            missing.append(f"{label} '{value}'")
        return found

    resolved = replace(
        cfg,
        gramps_id_field_id=await ident("custom_fields", "custom field", cfg.gramps_id_field_id),
        gramps_url_field_id=await ident("custom_fields", "custom field", cfg.gramps_url_field_id),
        date_qualifier_field_id=await ident("custom_fields", "custom field", cfg.date_qualifier_field_id),
        transcription_tag_id=await ident("tags", "tag", cfg.transcription_tag_id),
        attribute_fields=tuple([(await ident("custom_fields", "custom field", f), name)
                                for f, name in cfg.attribute_fields]),
    )
    if missing:
        raise NamesError(f"Paperless has no {', '.join(missing)} (paperless section of config.yaml)")
    return resolved


def _blank_fields(doc: dict, field_ids: set) -> list[dict]:
    return [{**cf, "value": None} if cf["field"] in field_ids else cf for cf in doc.get("custom_fields") or []]


async def release_document(paperless: PaperlessClient, cfg: SyncPaperlessConfig, doc_id: int) -> None:
    """Stop syncing a document: empty its Gramps ID and URL fields and take its sync tags off"""
    cfg = await resolve_names(paperless, cfg)
    try:
        doc = await paperless.get_document(doc_id)
    except PaperlessError as exc:
        if exc.status == 404:
            return
        raise
    keys = {cfg.gramps_id_field_id, cfg.gramps_url_field_id}
    if any(cf["field"] in keys and cf.get("value") for cf in doc.get("custom_fields") or []):
        await paperless.patch_custom_fields(doc_id, _blank_fields(doc, keys))
    sync_ids = {tid for name in cfg.sync_tags if (tid := await paperless.resolve_tag_id(name)) is not None}
    tags = doc.get("tags") or []
    if sync_ids & set(tags):
        await paperless.patch_tags(doc_id, [t for t in tags if t not in sync_ids])


async def registered_documents(gramps: GrampsClient) -> dict[str, str]:
    """{Paperless document id: Gramps media id} from the media objects' Paperless ID attributes"""
    out: dict[str, str] = {}
    for m in await gramps.list_media(keys="gramps_id,attribute_list"):
        for system, source_id in codes.sources_of(m):
            if system == "paperless" and m.get("gramps_id"):
                out.setdefault(source_id, m["gramps_id"])
    return out


async def sync(
    paperless: PaperlessClient,
    gramps: GrampsClient,
    cfg: SyncPaperlessConfig,
    apply: bool,
    doc_ids: Iterable[int] | None = None,
    selected: set[str] | None = None,
) -> AsyncIterator[SyncEvent]:
    """Every tagged document (or the given ones) against the Gramps media carrying its Paperless ID:
    create, version, title, date, mirrored attributes, checksum and transcription notes. A document
    whose media was deleted in Gramps is released instead of created again"""
    counts = {"created": 0, "skipped": 0, "versions_updated": 0, "titles_updated": 0,
              "dates_updated": 0, "attributes_updated": 0, "tx_created": 0, "tx_updated": 0,
              "links_repaired": 0, "released": 0, "errors": 0}

    if not (cfg.gramps_id_field_id and cfg.gramps_url_field_id):
        yield SyncEvent(kind="error", detail=(
            "paperless.gramps_id_field and gramps_url_field are not configured. Create a text "
            "and a URL custom field in Paperless and put their names in config.yaml."))
        yield SyncEvent(kind="summary", data=counts)
        return
    try:
        cfg = await resolve_names(paperless, cfg)
    except NamesError as exc:
        yield SyncEvent(kind="error", detail=str(exc))
        yield SyncEvent(kind="summary", data=counts)
        return

    sync_tag_ids = {tid for name in cfg.sync_tags if (tid := await paperless.resolve_tag_id(name)) is not None}
    if not sync_tag_ids:
        yield SyncEvent(kind="error", detail="no sync tags found in Paperless")
        yield SyncEvent(kind="summary", data=counts)
        return
    tx_tag = cfg.transcription_tag_id

    def _sync_tagged(doc: dict) -> bool:
        return bool(sync_tag_ids & set(doc.get("tags") or []))

    def _tx_tagged(doc: dict) -> bool:
        return bool(tx_tag and tx_tag in (doc.get("tags") or []))

    documents: list[dict] = []
    if doc_ids is not None:
        for did in doc_ids:
            try:
                doc = await paperless.get_document(did)
            except PaperlessError as exc:
                if exc.status != 404:
                    raise
                yield SyncEvent(kind="error", source_id=str(did),
                                detail=f"Paperless document #{did} not found")
                continue
            if _sync_tagged(doc) or _tx_tagged(doc):
                documents.append(doc)
            else:
                yield SyncEvent(kind="started", detail=f"document #{did} is not tagged for Gramps")
        if documents:
            yield SyncEvent(kind="started", detail=f"{len(documents)} tagged document(s)")
    else:
        documents = await paperless.list_documents_by_tags(list(sync_tag_ids))
        if tx_tag:
            known = {d["id"] for d in documents}
            documents += [d for d in await paperless.list_documents_by_tag(tx_tag) if d["id"] not in known]
        yield SyncEvent(kind="started", detail=f"{len(documents)} tagged document(s) in Paperless")

    q_options: dict[str, str] = {}
    q_field = cfg.date_qualifier_field_id
    if q_field and documents:
        try:
            q_options = await paperless.resolve_custom_field_options(q_field)
        except Exception as exc:  # noqa BLE001
            yield SyncEvent(kind="error", detail=f"date qualifier field options: {exc}")
            q_field = None

    attr_fields: list[tuple[int, str]] = []
    attr_options: dict[int, dict] = {}
    if cfg.attribute_fields and documents:
        for fid, name in cfg.attribute_fields:
            try:
                attr_options[fid] = await paperless.resolve_custom_field_options(fid)
            except Exception as exc:  # noqa BLE001
                yield SyncEvent(kind="error", detail=f"attribute field {fid} ({name}): {exc}")
                continue
            attr_fields.append((fid, name))

    def _wanted_attributes(doc: dict) -> dict[str, str | None]:
        return {name: attribute_value(PaperlessClient.custom_field_value(doc, fid), attr_options.get(fid))
                for fid, name in attr_fields}

    def _date_of(doc: dict) -> dict | None:
        if not q_field:
            return None
        q_val = paperless.custom_field_value(doc, q_field)
        return build_gramps_date(doc, q_options.get(q_val) if q_val else None)

    def _prospective_cols(doc: dict) -> dict:
        cols: dict = {}
        if _date_of(doc):
            cols["date"] = "new"
        if _tx_tagged(doc):
            content = (doc.get("content") or "").strip()
            if content:
                _tx, tl = split_transcription(content, cfg.translation_marker)
                cols["transcription"] = "new"
                if tl:
                    cols["translation"] = "new"
            else:
                cols["transcription"] = "tagged, no text yet"
        for name, value in _wanted_attributes(doc).items():
            if value is not None:
                cols[name] = "new"
        return cols

    paperless_codes: dict[str, list[int]] = {}
    for d in documents:
        if code := codes.normalize(_doc_gramps_id(d, cfg.gramps_id_field_id)):
            paperless_codes.setdefault(code, []).append(d["id"])

    live: set[str] | None = None
    registered: dict[str, str] | None = None
    note_ids: set[str] | None = None

    async def _live() -> set[str]:
        nonlocal live
        if live is None:
            live = await gramps.list_media_gramps_ids()
        return live

    async def _registered() -> dict[str, str]:
        nonlocal registered
        if registered is None:
            registered = await registered_documents(gramps)
        return registered

    async def _write_back(doc: dict, gid: str) -> None:
        updates = {cfg.gramps_id_field_id: gid,
                   cfg.gramps_url_field_id: f"{cfg.gramps_public_url}/media/{gid}"}
        cfs = [{**cf, "value": updates[cf["field"]]} if cf["field"] in updates else cf
               for cf in doc.get("custom_fields") or []]
        present = {cf["field"] for cf in cfs}
        cfs += [{"field": fid, "value": value} for fid, value in updates.items() if fid not in present]
        await paperless.patch_custom_fields(doc["id"], cfs)
        doc["custom_fields"] = cfs

    async def _note_id() -> str:
        nonlocal note_ids
        if note_ids is None:
            items = await gramps._paged("/notes/", keys="gramps_id")
            note_ids = {i["gramps_id"] for i in items if i.get("gramps_id")}
        nid = ids.next_sequential_id("N", note_ids)
        note_ids.add(nid)
        return nid

    total = len(documents)
    done = 0

    for doc in documents:
        yield progress("Checking documents", done, total)
        done += 1
        doc_id = doc["id"]
        title = doc.get("title", f"Untitled (Paperless #{doc_id})")
        keys = {f"doc:{doc_id}", f"media:{doc_id}", f"note:{doc_id}"}
        if selected is not None and not keys & selected:
            continue
        sync_tagged, tx_tagged = _sync_tagged(doc), _tx_tagged(doc)
        field_gid = gid = _doc_gramps_id(doc, cfg.gramps_id_field_id)

        def failed(entity: str, detail: str, **kw) -> SyncEvent:
            counts["errors"] += 1
            return SyncEvent(kind="item", entity=entity, action="failed", source_id=str(doc_id),
                             gramps_id=gid, title=title, detail=detail, **kw)

        media, adopted, taken_by_other = None, False, False
        try:
            if field_gid:
                found = await gramps.get_media_by_gramps_id(field_gid, notes=tx_tagged)
                owners = codes.sources_of(found) if found else []
                if found and ("paperless", str(doc_id)) in owners:
                    media = found
                elif found and not owners:
                    media, adopted = found, True
                elif found:
                    taken_by_other = True
            if media is None:
                known = (await _registered()).get(str(doc_id))
                if known:
                    media = await gramps.get_media_by_gramps_id(known, notes=tx_tagged)
        except Exception as exc:  # noqa BLE001
            yield failed("doc", f"Gramps lookup failed: {str(exc)[:200]}")
            continue
        if media is not None:
            gid = media["gramps_id"]
        notes = ((media.pop("extended", None) or {}).get("notes") or []) if media else []
        created = False

        if media is not None and sync_tagged:
            wanted_url = f"{cfg.gramps_public_url}/media/{gid}"
            stale_url = bool(cfg.gramps_public_url) and (
                PaperlessClient.custom_field_value(doc, cfg.gramps_url_field_id) != wanted_url)
            stale_fields = field_gid != gid or stale_url
            if adopted or stale_fields:
                rcols: dict = {}
                if adopted:
                    rcols["Paperless ID"] = "new"
                if field_gid != gid:
                    rcols["Gramps ID field"] = f"{field_gid or '(empty)'} → {gid}"
                if stale_url:
                    rcols["Gramps URL field"] = wanted_url
                if apply:
                    try:
                        if adopted:
                            media["attribute_list"] = [
                                *(media.get("attribute_list") or []),
                                _attr("Paperless URL", f"{cfg.public_url}/documents/{doc_id}/details"),
                                _attr("Paperless ID", str(doc_id))]
                            _stamp(media)
                            await gramps.update_media(media["handle"], media)
                            (await _registered())[str(doc_id)] = gid
                        if stale_fields:
                            await _write_back(doc, gid)
                    except Exception as exc:  # noqa BLE001
                        yield failed("doc", f"link not repaired: {str(exc)[:200]}")
                        continue
                counts["links_repaired"] += 1
                yield SyncEvent(kind="item", entity="doc", action="updated" if apply else "would_update",
                                source_id=str(doc_id), gramps_id=gid, title=title, data={"cols": rcols})

        if media is None:
            if not sync_tagged:
                counts["skipped"] += 1
                continue
            if taken_by_other:
                yield failed("doc", f"{field_gid} in its Gramps ID field belongs to another document or photo")
                continue
            if PaperlessClient.custom_field_value(doc, cfg.gramps_url_field_id):
                if apply:
                    try:
                        await release_document(paperless, cfg, doc_id)
                    except Exception as exc:  # noqa BLE001
                        yield failed("doc", f"not released: {str(exc)[:200]}")
                        continue
                counts["released"] += 1
                yield SyncEvent(kind="item", entity="doc", action="removed" if apply else "would_remove",
                                source_id=str(doc_id), gramps_id=field_gid, title=title,
                                detail="deleted in Gramps", data={"cols": {"sync": "stopped"}})
                continue
            try:
                metadata = await paperless.get_document_metadata(doc_id)
            except Exception as exc:  # noqa BLE001
                yield failed("doc", f"metadata fetch failed: {exc}")
                continue
            gramps_path = f"paperless/{metadata['media_filename']}"
            if not apply:
                counts["created"] += 1
                yield SyncEvent(kind="item", entity="doc", action="would_create",
                                source_id=str(doc_id), title=title,
                                data={"path": gramps_path, "cols": _prospective_cols(doc)})
                continue
            try:
                if gid and cfg.codes:
                    others = {c: [d for d in ds if d != doc_id] for c, ds in paperless_codes.items()}
                    gid = codes.check_code(gid, await _live(), {c: ds for c, ds in others.items() if ds})
                else:
                    gid = codes.new_id(cfg.codes, ids.taken_ids(await _live(), paperless_codes))
            except codes.CodeError as exc:
                yield failed("doc", exc.detail)
                continue
            media = {
                "_class": "Media",
                "handle": ids.generate_handle(),
                "gramps_id": gid,
                "desc": title,
                "path": gramps_path,
                "mime": _media_mime(metadata, doc),
                "private": False,
                "change": int(datetime.now(timezone.utc).timestamp()),
                "attribute_list": [
                    _attr("Paperless URL", f"{cfg.public_url}/documents/{doc_id}/details"),
                    _attr("Paperless ID", str(doc_id)),
                ],
            }
            if date_obj := _date_of(doc):
                media["date"] = date_obj
            mirror_attributes(media, _wanted_attributes(doc))
            try:
                await gramps.create_media(media)
            except Exception as exc:  # noqa BLE001
                yield failed("doc", str(exc))
                continue
            (await _live()).add(gid)
            (await _registered())[str(doc_id)] = gid
            try:
                await _write_back(doc, gid)
            except Exception as exc:  # noqa BLE001
                yield SyncEvent(
                    kind="error", source_id=str(doc_id),
                    detail=f"media {gid} created in Gramps; its ID is written to Paperless on the next sync ({exc})")
            counts["created"] += 1
            created = True
            yield SyncEvent(kind="item", entity="doc", action="created",
                            source_id=str(doc_id), gramps_id=gid, title=title,
                            data={"path": gramps_path, "cols": _prospective_cols(doc)})
            try:
                await gramps.store_checksum(media)
            except Exception as exc:  # noqa BLE001
                yield failed("doc", f"created, but Gramps could not read its file for the checksum: {exc}")

        if sync_tagged and not created:
            try:
                metadata = await paperless.get_document_metadata(doc_id)
            except Exception as exc:  # noqa BLE001
                yield failed("doc", f"version check failed: {exc}")
                continue
            new_path = f"paperless/{metadata['media_filename']}"
            new_mime = _media_mime(metadata, doc)
            if media.get("path") != new_path or media.get("mime") != new_mime:
                vcols: dict = {"version": f"{media.get('path') or '(none)'} → {new_path}"}
                if apply:
                    media["path"] = new_path
                    media["mime"] = new_mime
                    media["checksum"] = ""
                    _stamp(media)
                    try:
                        await gramps.update_media(media["handle"], media)
                        if await gramps.store_checksum(media):
                            vcols["checksum"] = "updated"
                    except Exception as exc:  # noqa BLE001
                        yield failed("doc", f"Gramps could not take the new version: {str(exc)[:200]}")
                        continue
                counts["versions_updated"] += 1
                yield SyncEvent(kind="item", entity="doc",
                                action="updated" if apply else "would_update",
                                source_id=str(doc_id), gramps_id=gid, title=title,
                                data={"cols": vcols})

            media_dirty = False
            mcols: dict = {}
            if media.get("desc") != title:
                mcols["title"] = f"{media.get('desc')!r} → {title!r}"
                if apply:
                    media["desc"] = title
                    media_dirty = True
                counts["titles_updated"] += 1
            date_obj = _date_of(doc)
            if date_obj is not None and not dates_equal(media.get("date") or {}, date_obj):
                mcols["date"] = ("changed" if format_gramps_date(media.get("date")) != "(none)"
                                 else "new")
                if apply:
                    media["date"] = date_obj
                    media_dirty = True
                counts["dates_updated"] += 1
            if attr_fields:
                wanted = _wanted_attributes(doc)
                acols = attribute_changes(media, wanted)
                if acols:
                    mcols.update(acols)
                    counts["attributes_updated"] += len(acols)
                    if apply:
                        mirror_attributes(media, wanted)
                        media_dirty = True
            if not media.get("checksum"):
                mcols["checksum"] = "missing"
                if apply:
                    try:
                        media["checksum"] = await gramps.media_md5(media["handle"])
                        media_dirty = True
                    except Exception as exc:  # noqa BLE001
                        del mcols["checksum"]
                        yield failed("doc", f"Gramps could not read the file for its checksum: {exc}")
            if media_dirty:
                _stamp(media)
                try:
                    await gramps.update_media(media["handle"], media)
                except Exception as exc:  # noqa BLE001
                    yield failed("doc", str(exc))
                    continue
            if mcols:
                yield SyncEvent(kind="item", entity="media",
                                action="updated" if apply else "would_update",
                                source_id=str(doc_id), gramps_id=gid, title=title,
                                data={"cols": mcols})

        if not (tx_tagged and gid):
            continue
        content = (doc.get("content") or "").strip()
        if not content:
            continue
        tx_text, tl_text = split_transcription(content, cfg.translation_marker)
        tx_note, tl_note = _note_of(notes, TX_NOTE), _note_of(notes, TL_NOTE)
        ncols: dict = {}
        if tx_note is None:
            ncols["transcription"] = "new"
        elif _text(tx_note).strip() != tx_text:
            ncols["transcription"] = "modified"
        if tl_text is not None:
            if tl_note is None:
                ncols["translation"] = "new"
            elif _text(tl_note).strip() != tl_text:
                ncols["translation"] = "modified"
        if not ncols:
            continue
        is_update = tx_note is not None
        if not apply:
            counts["tx_updated" if is_update else "tx_created"] += 1
            yield SyncEvent(kind="item", entity="note",
                            action="would_update" if is_update else "would_create",
                            source_id=str(doc_id), gramps_id=gid, title=title, data={"cols": ncols})
            continue
        try:
            new_handles: list[str] = []
            for col, note, text, kind in (("transcription", tx_note, tx_text, TX_NOTE),
                                          ("translation", tl_note, tl_text, TL_NOTE)):
                if col not in ncols:
                    continue
                if note is None:
                    handle = ids.generate_handle()
                    await gramps.create_note(build_note_obj(handle, await _note_id(), text, kind))
                    new_handles.append(handle)
                else:
                    await gramps.update_note(
                        note["handle"], build_note_obj(note["handle"], note["gramps_id"], text, kind))
            if new_handles:
                media["note_list"] = [*(media.get("note_list") or []), *new_handles]
                _stamp(media)
                await gramps.update_media(media["handle"], media)
        except Exception as exc:  # noqa BLE001
            yield failed("note", str(exc))
            continue
        counts["tx_updated" if is_update else "tx_created"] += 1
        yield SyncEvent(kind="item", entity="note", action="updated" if is_update else "created",
                        source_id=str(doc_id), gramps_id=gid, title=title, data={"cols": ncols})

    if total:
        yield progress("Checking documents", done, total)
    yield SyncEvent(kind="summary", data=counts)
