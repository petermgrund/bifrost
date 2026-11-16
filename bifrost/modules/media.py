"""Deleting and merging the media objects Bifrost added to Gramps"""

from __future__ import annotations

import logging

from ..core.clients import GrampsClient
from ..core.config import Config
from . import codes, sync_immich, sync_paperless
from .codes import CodeError

log = logging.getLogger("bifrost.media")

OWN_NOTES = frozenset({sync_paperless.TX_NOTE, sync_paperless.TL_NOTE, sync_immich.NOTE_TYPE})


async def _media(gramps: GrampsClient, raw: str | None) -> dict:
    gid = codes.normalize(raw)
    media = await gramps.get_media_by_gramps_id(gid, backlinks=True, notes=True) if gid else None
    if media is None:
        raise CodeError(404, f"{gid or 'That'} is not a Gramps media object.")
    return media


async def release(gramps: GrampsClient, media: dict, paperless, accounts: list, cfg: Config) -> list[str]:
    """Stop syncing the media's sources unless another media object still shows them;
    what could not be undone there, as sentences"""
    problems = []
    shown = {source for m in await gramps.list_media(keys="gramps_id,attribute_list")
             for source in codes.sources_of(m)}
    for system, source_id in codes.sources_of(media):
        if (system, source_id) in shown:
            continue
        try:
            if system == "paperless" and paperless is not None and source_id.isdecimal():
                await sync_paperless.release_document(paperless, cfg.sync_paperless, int(source_id))
            elif system == "immich" and accounts:
                await sync_immich.release_asset(accounts, cfg.sync_immich, source_id)
        except Exception as exc:  # noqa: BLE001
            log.warning("release of %s %s failed: %s", system, source_id, exc)
            name = "Paperless document" if system == "paperless" else "Immich photo"
            problems.append(f"{name} {source_id} still carries its sync marks; the next sync check removes them.")
    return problems


async def delete(gramps: GrampsClient, paperless, accounts: list, cfg: Config, raw: str | None,
                 media: dict | None = None) -> dict:
    """Remove the media object and its Bifrost notes from Gramps, then release its sources"""
    media = media or await _media(gramps, raw)
    notes = (media.get("extended") or {}).get("notes") or []
    await gramps.delete_media(media["handle"])
    for note in notes:
        if note.get("type") in OWN_NOTES:
            try:
                await gramps.delete_note(note["handle"])
            except Exception as exc:  # noqa: BLE001
                log.warning("note %s of %s not deleted: %s", note.get("gramps_id"), media["gramps_id"], exc)
    return {"code": media["gramps_id"], "problems": await release(gramps, media, paperless, accounts, cfg)}


async def merge(gramps: GrampsClient, paperless, accounts: list, cfg: Config,
                raw: str | None, raw_into: str | None) -> dict:
    """Point everything that shows the first media at the second, which keeps a record of the
    first's ID (and of the IDs merged into it earlier), then delete the first"""
    gone, kept = await _media(gramps, raw), await _media(gramps, raw_into)
    if gone["handle"] == kept["handle"]:
        raise CodeError(400, "Choose two different media objects.")
    moved = 0
    for kind, api_path in sync_paperless.BACKLINK_OBJ_TYPES.items():
        for handle in (gone.get("backlinks") or {}).get(kind) or []:
            obj = await gramps.get_object(api_path, handle)
            refs = obj.get("media_list") or []
            has_kept = any(r.get("ref") == kept["handle"] for r in refs)
            merged = []
            for ref in refs:
                if ref.get("ref") != gone["handle"]:
                    merged.append(ref)
                elif not has_kept:
                    merged.append({**ref, "ref": kept["handle"]})
                    has_kept = True
            if merged != refs:
                obj["media_list"] = merged
                await gramps.update_object(api_path, handle, obj)
                moved += 1
    record = list(dict.fromkeys([*codes.merged_ids(kept), *codes.merged_ids(gone), gone["gramps_id"]]))
    if record != codes.merged_ids(kept):
        others = [a for a in kept.get("attribute_list") or [] if a.get("type") != codes.MERGED_ATTR]
        body = {k: v for k, v in kept.items() if k not in ("backlinks", "extended")}
        body["attribute_list"] = others + [sync_paperless._attr(codes.MERGED_ATTR, gid) for gid in record]
        await gramps.update_media(kept["handle"], body)
    result = await delete(gramps, paperless, accounts, cfg, None, media=gone)
    return {**result, "into": kept["gramps_id"], "moved": moved}
