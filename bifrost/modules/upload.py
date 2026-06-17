"""Upload-wizard orchestration: ingest a Paperless doc, edit its metadata
(house-style autofill), mint a Gramps media object, hand off to the citation
pipeline. Reuses ocr.run, sync_paperless.sync, and the Paperless client — this
module only glues them together and shapes the form payloads.

Web layering: routes own run-logging (record_run); functions here that consume a
generator take the already-collected events as a plain list, so this module
never imports the web package.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..core.clients import GrampsClient, PaperlessClient
from ..core.clients.anthropic import AnthropicClient
from ..core.config import SyncPaperlessConfig
from ..core.events import SyncEvent

# Form field <-> Paperless custom field id, resolved from config at call time.
# (document title/created/correspondent/document_type/tags are NOT custom fields.)

_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".tif", ".tiff",
              ".heic", ".heif", ".bmp"}


def _kind(name: str, mime: str = "") -> str:
    """pdf | image | other — drives <iframe> vs <img> in the preview pane."""
    mime = (mime or "").lower()
    if "pdf" in mime:
        return "pdf"
    if mime.startswith("image/"):
        return "image"
    ext = Path(name or "").suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext in _IMAGE_EXT:
        return "image"
    return "other"


def _normalize_date(raw: str | None) -> str | None:
    """A YYYY-MM-DD string from a partial input. Year-only -> Jan 1, year-month
    -> the 1st, per the house-style date rule. None if unparseable/blank."""
    if not raw:
        return None
    s = str(raw).strip()[:10]
    if re.fullmatch(r"\d{4}", s):
        return f"{s}-01-01"
    if re.fullmatch(r"\d{4}-\d{2}", s):
        return f"{s}-01"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    return None


# ----------------------------------------------------------------------------
# Ingest
# ----------------------------------------------------------------------------

async def ingest(
    paperless: PaperlessClient, cfg: SyncPaperlessConfig,
    filename: str, data: bytes, mime: str, ocr: bool,
) -> str:
    """Push bytes into Paperless. Always tags with the first sync tag (so the
    doc is later eligible for the Gramps sync); if `ocr`, also adds the Gemini
    OCR tag so ocr.run picks it up. Returns the consume task uuid."""
    tag_ids: list[int] = []
    if cfg.sync_tags:
        tid = await paperless.resolve_tag_id(cfg.sync_tags[0])
        if tid is not None:
            tag_ids.append(tid)
    if not tag_ids:
        # Without a sync tag the doc could never be carried to Gramps later
        # (sync only sees tagged docs) — fail loudly instead of orphaning it.
        raise ValueError(
            f"sync tag '{cfg.sync_tags[0] if cfg.sync_tags else ''}' not found in "
            "Paperless — create it before uploading so the document can reach Gramps")
    if ocr and cfg.ocr_tag:
        otid = await paperless.resolve_tag_id(cfg.ocr_tag)
        if otid is not None and otid not in tag_ids:
            tag_ids.append(otid)
    return await paperless.upload(filename, data, mime, tag_ids)


async def ingest_status(paperless: PaperlessClient, task_uuid: str) -> dict:
    """Map a Paperless consume task to {status, doc_id, error}."""
    task = await paperless.get_task(task_uuid)
    status = (task.get("status") or "PENDING").upper()
    doc_id = task.get("related_document")
    out = {"status": status, "doc_id": int(doc_id) if doc_id else None}
    # REVOKED is terminal too — collapse it to FAILURE so the poller stops.
    if status in ("FAILURE", "REVOKED"):
        out["status"] = "FAILURE"
        out["error"] = task.get("result") or (
            "consume was revoked" if status == "REVOKED"
            else "consume failed (often a duplicate)")
    return out


async def ensure_ocr_tag(paperless: PaperlessClient, cfg: SyncPaperlessConfig,
                         doc_id: int) -> bool:
    """Make sure the doc carries the Gemini OCR tag so ocr.run selects it.
    Returns False if no OCR tag is configured/resolvable."""
    if not cfg.ocr_tag:
        return False
    tag_id = await paperless.resolve_tag_id(cfg.ocr_tag)
    if not tag_id:
        return False
    doc = await paperless.get_document(doc_id)
    tags = doc.get("tags") or []
    if tag_id not in tags:
        await paperless.patch_tags(doc_id, sorted(set(tags) | {tag_id}))
    return True


async def read_transcript(paperless: PaperlessClient, doc_id: int) -> dict:
    """The doc's current searchable text (the OCR output)."""
    doc = await paperless.get_document(doc_id)
    text = (doc.get("content") or "").strip()
    return {"chars": len(text), "transcript": text}


def ocr_errors(events: list[SyncEvent]) -> list[str]:
    """Pull failure detail out of an ocr.run event list."""
    return [e.detail for e in events
            if (e.kind == "error" or e.action == "failed") and e.detail]


# ----------------------------------------------------------------------------
# Form options + load/save
# ----------------------------------------------------------------------------

def _select_specs(cfg: SyncPaperlessConfig) -> dict[str, int | None]:
    return {
        "date_meaning": cfg.date_meaning_field_id,
        "date_qualifier": cfg.date_qualifier_field_id,
        "family_group": cfg.family_group_field_id,
        "source_url_access": cfg.source_url_access_field_id,
    }


async def options(paperless: PaperlessClient, cfg: SyncPaperlessConfig) -> dict:
    """Dropdown data for the form: correspondents, document types, tags, and the
    select custom fields as ordered [{id,label}] lists."""
    selects: dict[str, list[dict]] = {}
    for key, fid in _select_specs(cfg).items():
        if not fid:
            selects[key] = []
            continue
        opts = await paperless.resolve_custom_field_options(fid)
        selects[key] = [{"id": oid, "label": label} for oid, label in opts.items()]
    return {
        "correspondents": await paperless.list_correspondents(),
        "document_types": await paperless.list_document_types(),
        "tags": await paperless.list_tags(),
        "selects": selects,
    }


def _form_from_doc(doc: dict, cfg: SyncPaperlessConfig) -> dict:
    g = PaperlessClient.get_custom_field_value
    created = (doc.get("created") or doc.get("created_date") or "")[:10]
    return {
        "title": doc.get("title") or "",
        "date": created,
        "document_type": doc.get("document_type"),
        "correspondent": doc.get("correspondent"),
        "tags": list(doc.get("tags") or []),
        "date_meaning": g(doc, cfg.date_meaning_field_id) if cfg.date_meaning_field_id else None,
        "date_qualifier": g(doc, cfg.date_qualifier_field_id) if cfg.date_qualifier_field_id else None,
        "family_group": g(doc, cfg.family_group_field_id) if cfg.family_group_field_id else None,
        "source_url": g(doc, cfg.source_url_field_id) if cfg.source_url_field_id else None,
        "source_url_access": g(doc, cfg.source_url_access_field_id) if cfg.source_url_access_field_id else None,
    }


async def load_doc(paperless: PaperlessClient, cfg: SyncPaperlessConfig,
                   doc_id: int) -> dict:
    """Prefill payload for an EXISTING Paperless doc. Raises if it is already in
    Gramps (has a Gramps ID) — those must not be re-synced/duplicated."""
    doc = await paperless.get_document(doc_id)
    if cfg.gramps_id_field_id and PaperlessClient.get_custom_field_value(
            doc, cfg.gramps_id_field_id):
        raise ValueError("this document already has a Gramps ID — it is already in Gramps")
    form = _form_from_doc(doc, cfg)
    sync_tag_ids = await _sync_tag_ids(paperless, cfg)
    # Guarantee a sync tag so the to-Gramps step can find it later.
    if sync_tag_ids and not (set(form["tags"]) & set(sync_tag_ids)):
        form["tags"] = sorted(set(form["tags"]) | {sync_tag_ids[0]})
    transcript = (doc.get("content") or "").strip()
    return {
        "doc_id": doc_id,
        "form": form,
        "has_transcript": bool(transcript),
        "transcript": transcript,
        "kind": _kind(doc.get("original_file_name") or "", doc.get("mime_type") or ""),
    }


async def _sync_tag_ids(paperless: PaperlessClient,
                        cfg: SyncPaperlessConfig) -> list[int]:
    ids: list[int] = []
    for name in cfg.sync_tags:
        tid = await paperless.resolve_tag_id(name)
        if tid is not None:
            ids.append(tid)
    return ids


async def list_candidates(paperless: PaperlessClient,
                          cfg: SyncPaperlessConfig) -> list[dict]:
    """Paperless docs WITHOUT a Gramps ID — the existing-doc picker. Excludes
    anything already synced into Gramps so it can't be duplicated."""
    fid = cfg.gramps_id_field_id
    docs = await paperless.list_all_documents()
    out = []
    for d in docs:
        if fid and PaperlessClient.get_custom_field_value(d, fid):
            continue
        out.append({
            "id": d["id"],
            "title": d.get("title") or f"Untitled #{d['id']}",
            "created": (d.get("created") or "")[:10],
            "correspondent": d.get("correspondent"),
            "tags": list(d.get("tags") or []),
        })
    out.sort(key=lambda r: r["created"], reverse=True)
    return out


async def save_fields(paperless: PaperlessClient, cfg: SyncPaperlessConfig,
                      doc_id: int, form: dict) -> None:
    """PATCH the form onto the Paperless doc — document fields + the five managed
    custom fields, round-tripping any custom fields we don't manage."""
    payload: dict = {}
    if "title" in form:
        payload["title"] = form.get("title") or ""
    created = _normalize_date(form.get("date"))
    if created:
        payload["created"] = created
    if "document_type" in form:
        payload["document_type"] = form.get("document_type") or None
    if "correspondent" in form:
        payload["correspondent"] = form.get("correspondent") or None
    if "tags" in form:
        payload["tags"] = [int(t) for t in (form.get("tags") or [])]

    managed = {
        cfg.date_meaning_field_id: form.get("date_meaning"),
        cfg.date_qualifier_field_id: form.get("date_qualifier"),
        cfg.family_group_field_id: form.get("family_group"),
        cfg.source_url_field_id: form.get("source_url"),
        cfg.source_url_access_field_id: form.get("source_url_access"),
    }
    managed = {fid: (val or None) for fid, val in managed.items() if fid}
    if managed:
        doc = await paperless.get_document(doc_id)
        cfs = list(doc.get("custom_fields") or [])
        seen: set[int] = set()
        for cf in cfs:
            if cf["field"] in managed:
                cf["value"] = managed[cf["field"]]
                seen.add(cf["field"])
        for fid, val in managed.items():
            if fid not in seen:
                cfs.append({"field": fid, "value": val})
        payload["custom_fields"] = cfs

    if payload:
        await paperless.patch_fields(doc_id, payload)


# ----------------------------------------------------------------------------
# House-style autofill (Anthropic, text-only)
# ----------------------------------------------------------------------------

_AUTOFILL_SYSTEM = (
    "You assign Paperless archive metadata for a genealogy document, following "
    "the house-style rules below EXACTLY. You are given the document's OCR "
    "transcript. Return your best-guess value for each field per the rules; OMIT "
    "any field you cannot determine from the transcript. For selects, use ONLY a "
    "value from the provided list. Dates: output YYYY-MM-DD (year-only -> "
    "YYYY-01-01) and set the date qualifier to match the precision. The "
    "correspondent is the digital provider/platform that hosts the record image."
    "\n\n===== PAPERLESS HOUSE STYLE =====\n\n"
)


def _labels(items: list[dict], key: str) -> list[str]:
    return [i[key] for i in items if i.get(key)]


def _form_schema(opts: dict) -> dict:
    sel = opts["selects"]
    props = {
        "title": {"type": "string",
                  "description": "Paperless filing title per the Title rules."},
        "date": {"type": "string",
                 "description": "Document date, YYYY-MM-DD (year-only -> YYYY-01-01)."},
        "source_url": {"type": "string",
                       "description": "Deep URL to the specific record image, if present."},
    }
    enum_map = {
        "date_meaning": _labels(sel.get("date_meaning", []), "label"),
        "date_qualifier": _labels(sel.get("date_qualifier", []), "label"),
        "family_group": _labels(sel.get("family_group", []), "label"),
        "source_url_access": _labels(sel.get("source_url_access", []), "label"),
        "document_type": _labels(opts.get("document_types", []), "name"),
        "correspondent": _labels(opts.get("correspondents", []), "name"),
    }
    for key, values in enum_map.items():
        if values:
            props[key] = {"type": "string", "enum": values}
    return {"type": "object", "properties": props}


def _id_for_label(items: list[dict], label: str, label_key: str) -> object:
    if not label:
        return None
    low = label.strip().lower()
    for i in items:
        if (i.get(label_key) or "").strip().lower() == low:
            return i["id"]
    # Tolerate a near-miss (e.g. a trailing qualifier the model appended) via a
    # safe prefix match — but never a loose substring, which could mis-map.
    for i in items:
        name = (i.get(label_key) or "").strip().lower()
        if name and (name.startswith(low) or low.startswith(name)):
            return i["id"]
    return None


async def autofill(anthropic: AnthropicClient, transcript: str,
                   house_style: str, opts: dict) -> dict:
    """Opus guesses the form fields from the transcript + house style. Returns
    the SAME representation the form uses (ids for selects/doc-type/correspondent,
    strings for free text); only keys it could fill are present."""
    if not transcript.strip():
        raise ValueError("no transcript to autofill from — run OCR first")
    schema = _form_schema(opts)
    raw = await anthropic.complete_structured(
        system=_AUTOFILL_SYSTEM + house_style, user=transcript,
        schema=schema, max_tokens=2000)

    sel = opts["selects"]
    out: dict = {}
    if raw.get("title"):
        out["title"] = raw["title"]
    if raw.get("date"):
        out["date"] = _normalize_date(raw["date"]) or raw["date"]
    if raw.get("source_url"):
        out["source_url"] = raw["source_url"]
    for key in ("date_meaning", "date_qualifier", "family_group", "source_url_access"):
        oid = _id_for_label(sel.get(key, []), raw.get(key, ""), "label")
        if oid is not None:
            out[key] = oid
    dt = _id_for_label(opts.get("document_types", []), raw.get("document_type", ""), "name")
    if dt is not None:
        out["document_type"] = dt
    co = _id_for_label(opts.get("correspondents", []), raw.get("correspondent", ""), "name")
    if co is not None:
        out["correspondent"] = co
    return out


def paperless_house_style(path: str | Path) -> str:
    """Extract the Paperless-relevant slices of the house-style master, by header
    marker (robust to line shifts): the Gramps field map + Part A subject-
    formatting (Title rules Part C defers to) + all of Part C."""
    p = Path(path)
    if not p.is_file():
        return ""
    text = p.read_text(encoding="utf-8")
    field_map = _slice(text, "## Gramps field map", ("## ", "# "))
    subject = _slice(text, "## Subject formatting in the page string", ("## ", "# "))
    part_c = _slice(text, "# Part C", ("# ",))
    chunks = [c for c in (field_map, subject, part_c) if c]
    return "\n\n".join(chunks)


def _slice(text: str, header: str, stop_prefixes: tuple[str, ...]) -> str:
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.startswith(header)), None)
    if start is None:
        return ""
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if any(lines[j].startswith(pre) for pre in stop_prefixes):
            end = j
            break
    return "\n".join(lines[start:end]).strip()


# ----------------------------------------------------------------------------
# To Gramps (mint the media object)
# ----------------------------------------------------------------------------

async def resolve_minted(paperless: PaperlessClient, gramps: GrampsClient,
                         cfg: SyncPaperlessConfig, doc_id: int,
                         events: list[SyncEvent]) -> dict:
    """After a single-doc Paperless->Gramps sync, resolve the new media object's
    handle. Prefers the gramps_id from the run's created event; falls back to the
    Gramps-ID custom field written back onto the doc."""
    gid = next(
        (e.gramps_id for e in events
         if e.kind == "item" and e.action == "created"
         and e.source_id == str(doc_id) and e.gramps_id),
        None)
    if not gid and cfg.gramps_id_field_id:
        doc = await paperless.get_document(doc_id)
        gid = PaperlessClient.get_custom_field_value(doc, cfg.gramps_id_field_id)
    if not gid:
        errs = [e.detail for e in events
                if (e.kind == "error" or e.action == "failed") and e.detail]
        raise ValueError("; ".join(errs) or "no media object was created")
    media = await gramps.get_media_by_gramps_id(str(gid))
    if not media:
        raise ValueError(f"media {gid} created but could not be looked up")
    return {
        "media_handle": media["handle"],
        "gramps_id": str(gid),
        "desc": media.get("desc") or str(gid),
    }
