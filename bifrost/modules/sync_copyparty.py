"""copyparty files to Gramps media"""

from __future__ import annotations

import mimetypes
import posixpath
from datetime import datetime, timezone
from typing import AsyncIterator
from urllib.parse import quote, unquote

from ..core import ids
from ..core.clients import CopypartyClient, GrampsClient
from ..core.config import SyncCopypartyConfig
from ..core.events import SyncEvent, progress
from . import codes
from .codes import FILE_ATTR
from .sync_paperless import _attr, _stamp

MIMES = {".m4a": "audio/mp4", ".m4b": "audio/mp4", ".flac": "audio/flac", ".ogg": "audio/ogg",
         ".oga": "audio/ogg", ".mka": "audio/x-matroska", ".geojson": "application/geo+json",
         ".gpx": "application/gpx+xml"}
MEDIA_KEYS = "handle,gramps_id,desc,path,checksum,attribute_list"


def mime_of(name: str) -> str:
    ext = posixpath.splitext(name)[1].lower()
    return MIMES.get(ext) or mimetypes.guess_type(name)[0] or "application/octet-stream"


def file_of(path: str, folder: str, prefix: str, public_url: str) -> dict:
    """A copyparty file as Gramps sees it: where its bytes are, its link and the code its name spells"""
    name = posixpath.basename(path)
    stem = posixpath.splitext(name)[0]
    return {
        "path": path,
        "name": name,
        "stem": stem,
        "gramps_path": prefix + (path[len(folder):].lstrip("/") if folder else path),
        "url": f"{public_url}/{quote(path)}",
        "code": stem if ids.MANUAL_ID_RE.match(stem) and not ids.guard_reason(stem) else None,
    }


def links_of(media: dict) -> list[str]:
    return [a["value"] for a in media.get("attribute_list") or []
            if a.get("type") == FILE_ATTR and a.get("value")]


def set_links(media: dict, urls: list[str]) -> bool:
    """Replace the media's Copyparty URL attributes, other attributes kept; True when they changed"""
    if links_of(media) == urls:
        return False
    kept = [a for a in media.get("attribute_list") or [] if a.get("type") != FILE_ATTR]
    media["attribute_list"] = kept + [_attr(FILE_ATTR, url) for url in urls]
    return True


def _stem(path: str) -> str:
    return posixpath.splitext(posixpath.basename(path))[0]


async def sync(
    copyparty: CopypartyClient,
    gramps: GrampsClient,
    cfg: SyncCopypartyConfig,
    apply: bool,
    selected: set[str] | None = None,
) -> AsyncIterator[SyncEvent]:
    """Every file under the mapped copyparty folders against Gramps: a new file becomes a media object
    pointing at it in place, a moved file is followed, a file named after a media's code is linked from it"""
    counts = {"created": 0, "files_moved": 0, "files_linked": 0, "errors": 0}

    def failed(detail: str, **row) -> SyncEvent:
        counts["errors"] += 1
        return SyncEvent(kind="item", action="failed", detail=detail[:300], **row)

    try:
        listed = [file_of(f["path"], folder, prefix, cfg.public_url)
                  for folder, prefix in cfg.path_mappings for f in await copyparty.walk(folder)]
    except Exception as exc:  # noqa: BLE001
        counts["errors"] += 1
        yield SyncEvent(kind="error", detail=f"copyparty: {str(exc)[:200]}")
        yield SyncEvent(kind="summary", data=counts)
        return
    try:
        media = await gramps.list_media(keys=MEDIA_KEYS)
    except Exception as exc:  # noqa: BLE001
        counts["errors"] += 1
        yield SyncEvent(kind="error", detail=f"Gramps could not be read: {str(exc)[:200]}")
        yield SyncEvent(kind="summary", data=counts)
        return

    files = {f["gramps_path"]: f for f in listed}
    prefixes = tuple(prefix for _folder, prefix in cfg.path_mappings)
    by_gid = {m["gramps_id"]: m for m in media if m.get("gramps_id")}
    backed = {m["path"]: m for m in media if (m.get("path") or "").startswith(prefixes)}
    orphans = {p: m for p, m in backed.items() if p not in files}
    yield SyncEvent(kind="started", detail=f"{len(files)} file(s) in copyparty; {len(backed)} synced media")

    moves: list[tuple[dict, dict]] = []
    rest: list[dict] = []
    for path, f in files.items():
        if path in backed:
            continue
        m = by_gid.get(f["code"]) if f["code"] else None
        if m is not None and orphans.get(m.get("path") or "") is m:
            moves.append((orphans.pop(m["path"]), f))
        else:
            rest.append(f)
    by_md5 = {m["checksum"]: p for p, m in orphans.items() if m.get("checksum")}
    creates: list[dict] = []
    claimed: set[str] = set()
    for f in rest:
        code = f["code"]
        if code and (code in by_gid or code in claimed):
            continue
        found = None
        if by_md5:
            try:
                found = by_md5.pop(await copyparty.md5(f["path"]), None)
            except Exception:  # noqa: BLE001
                found = None
        if found is not None:
            moves.append((orphans.pop(found), f))
            continue
        creates.append(f)
        if code:
            claimed.add(code)

    backing = {m["gramps_id"]: files[p] for p, m in backed.items() if p in files}

    def wanted_links(gid: str, own: dict | None) -> list[str]:
        named = [f for f in files.values() if f["code"] == gid and f is not own]
        return [f["url"] for f in ([own] if own else []) + named]

    def chosen(key: str) -> bool:
        return selected is None or key in selected

    total = len(creates) + len(moves)
    done = 0
    live = set(by_gid)
    withdrawn = await codes.withdrawn(gramps) if creates else {}
    taken = ids.taken_ids(live, withdrawn, (f["code"] for f in files.values()))

    for f in creates:
        yield progress("Checking files", done, total)
        done += 1
        row = dict(entity="file", source_id=f["path"], title=f["name"])
        try:
            gid = codes.check_code(f["code"], live, withdrawn) if f["code"] else None
        except codes.CodeError as exc:
            yield failed(exc.detail, gramps_id=f["code"], **row)
            continue
        cols = {"title": f["stem"]}
        if not apply:
            counts["created"] += 1
            yield SyncEvent(kind="item", action="would_create", gramps_id=gid, data={"cols": cols}, **row)
            continue
        if not chosen(f"file:{f['path']}"):
            continue
        gid = gid or ids.generate_gramps_id(taken)
        new = {
            "_class": "Media",
            "handle": ids.generate_handle(),
            "gramps_id": gid,
            "desc": f["stem"],
            "path": f["gramps_path"],
            "mime": mime_of(f["name"]),
            "private": False,
            "change": int(datetime.now(timezone.utc).timestamp()),
            "attribute_list": [_attr(FILE_ATTR, url) for url in wanted_links(gid, f)],
        }
        try:
            await gramps.create_media(new)
        except Exception as exc:  # noqa: BLE001
            yield failed(str(exc), gramps_id=gid, **row)
            continue
        live.add(gid)
        backing[gid] = f
        counts["created"] += 1
        yield SyncEvent(kind="item", action="created", gramps_id=gid, data={"cols": cols}, **row)
        try:
            await gramps.store_checksum(new)
        except Exception as exc:  # noqa: BLE001
            yield failed(f"created, but Gramps could not read its file for the checksum: {exc}",
                         gramps_id=gid, **row)

    for m, f in moves:
        yield progress("Checking files", done, total)
        done += 1
        gid = m["gramps_id"]
        row = dict(entity="file", source_id=f["path"], gramps_id=gid, title=m.get("desc") or f["name"])
        cols = {"file": f"{m['path']} → {f['gramps_path']}"}
        if not apply:
            counts["files_moved"] += 1
            yield SyncEvent(kind="item", action="would_update", data={"cols": cols}, **row)
            continue
        if not chosen(f"file:{f['path']}"):
            continue
        try:
            full = await gramps.get_media_by_gramps_id(gid)
            if full.get("desc") == _stem(m["path"]) != f["stem"]:
                full["desc"] = f["stem"]
                cols["title"] = f["stem"]
            full["path"], full["mime"], full["checksum"] = f["gramps_path"], mime_of(f["name"]), ""
            set_links(full, wanted_links(gid, f))
            _stamp(full)
            await gramps.update_media(full["handle"], full)
            await gramps.store_checksum(full)
        except Exception as exc:  # noqa: BLE001
            yield failed(f"Gramps could not follow the file: {exc}", **row)
            continue
        backing[gid] = f
        counts["files_moved"] += 1
        yield SyncEvent(kind="item", action="updated", data={"cols": cols}, **row)

    moved = {m["gramps_id"] for m, _f in moves}
    for m in media:
        gid = m.get("gramps_id")
        if not gid or gid in moved:
            continue
        if orphans.get(m.get("path") or "") is m:
            yield failed("its file is gone from copyparty", entity="file", source_id=m["path"],
                         gramps_id=gid, title=m.get("desc") or gid)
            continue
        own = backing.get(gid)
        want = wanted_links(gid, own)
        cols: dict = {}
        if links_of(m) != want:
            cols["link"] = ", ".join(posixpath.basename(unquote(url)) for url in want) or "removed"
        if own is not None and not m.get("checksum"):
            cols["checksum"] = "missing"
        if not cols:
            continue
        row = dict(entity="file" if own else "media", source_id=own["path"] if own else gid,
                   gramps_id=gid, title=m.get("desc") or gid)
        if not apply:
            counts["files_linked"] += "link" in cols
            yield SyncEvent(kind="item", action="would_update", data={"cols": cols}, **row)
            continue
        if not chosen(f"{row['entity']}:{row['source_id']}"):
            continue
        try:
            full = await gramps.get_media_by_gramps_id(gid)
            dirty = set_links(full, want)
            if "checksum" in cols:
                full["checksum"] = await gramps.media_md5(full["handle"])
                dirty = True
            if dirty:
                _stamp(full)
                await gramps.update_media(full["handle"], full)
        except Exception as exc:  # noqa: BLE001
            yield failed(str(exc), **row)
            continue
        counts["files_linked"] += "link" in cols
        yield SyncEvent(kind="item", action="updated", data={"cols": cols}, **row)

    if total:
        yield progress("Checking files", done, total)
    yield SyncEvent(kind="summary", data=counts)
