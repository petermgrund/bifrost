"""Gemini OCR"""

from __future__ import annotations

import io
from typing import AsyncIterator

from pypdf import PdfReader, PdfWriter

from ..core.clients import GeminiClient, GeminiError, PaperlessClient
from ..core.config import GeminiConfig, SyncPaperlessConfig
from ..core.events import SyncEvent
from .sync_paperless import _doc_gramps_id

OCR_PROMPT = """You are transcribing a historical or genealogical document \
image. It may be handwritten, old printed type, or a photograph of a record.

Transcribe all text exactly as it appears. Preserve the original spelling, \
capitalization, punctuation, diacritics, line breaks, and language. Do not \
translate or modernize. Transcribe both handwritten and printed text. For a \
genuinely illegible word write [illegible]; for an uncertain reading write the \
best guess followed by a question mark in brackets, e.g. Andersson[?].

Output only the transcription. Do not include any preamble, commentary, or markdown."""

_OK_MIME = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif",
            "application/pdf"}

CHUNK_PAGES = 30


def _pdf_pages(data: bytes) -> int | None:
    try:
        return len(PdfReader(io.BytesIO(data)).pages)
    except Exception:  # noqa BLE001
        return None


def _pdf_subset(reader: PdfReader, lo: int, hi: int) -> bytes:
    writer = PdfWriter()
    for i in range(lo, hi):
        writer.add_page(reader.pages[i])
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


async def _transcribe_range(
    gemini: GeminiClient, reader: PdfReader, lo: int, hi: int,
    prompt: str, thinking_budget: int | None,
) -> str:
    chunk = _pdf_subset(reader, lo, hi)
    try:
        return await gemini.transcribe(chunk, "application/pdf", prompt, thinking_budget)
    except GeminiError as exc:
        if "MAX_TOKENS" in str(exc) and hi - lo > 1:
            mid = (lo + hi) // 2
            first = await _transcribe_range(gemini, reader, lo, mid, prompt, thinking_budget)
            second = await _transcribe_range(gemini, reader, mid, hi, prompt, thinking_budget)
            return f"{first}\n\n{second}"
        raise


async def transcribe_document(
    gemini: GeminiClient, data: bytes, mime: str, prompt: str,
    thinking_budget: int | None,
) -> str:
    if mime != "application/pdf":
        return await gemini.transcribe(data, mime, prompt, thinking_budget)
    pages = _pdf_pages(data)
    if not pages or pages <= 1:
        return await gemini.transcribe(data, mime, prompt, thinking_budget)
    reader = PdfReader(io.BytesIO(data))
    parts: list[str] = []
    for lo in range(0, pages, CHUNK_PAGES):
        parts.append(await _transcribe_range(
            gemini, reader, lo, min(lo + CHUNK_PAGES, pages), prompt, thinking_budget))
    return "\n\n".join(p for p in parts if p)


def _current_text(doc: dict) -> str:
    return (doc.get("content") or "").strip()


def _no_transcript(text: str) -> bool:
    """Empty or a lone dash"""
    return text in ("", "-")


async def run(
    paperless: PaperlessClient,
    gemini: GeminiClient,
    cfg: SyncPaperlessConfig,
    gem_cfg: GeminiConfig,
    apply: bool,
    docs: list[dict] | None = None,
    selected: set[str] | None = None,
) -> AsyncIterator[SyncEvent]:
    """OCR the documents carrying the OCR tag: Create when empty, Replace otherwise"""
    counts = {"transcribed": 0, "replaced": 0, "errors": 0}

    if not cfg.ocr_tag:
        yield SyncEvent(kind="error", detail="no OCR tag configured (sync.paperless.ocr_tag)")
        yield SyncEvent(kind="summary", data=counts)
        return
    if apply and not gemini.configured:
        yield SyncEvent(kind="error", detail="no Gemini API key configured")
        yield SyncEvent(kind="summary", data=counts)
        return

    tag_id = await paperless.resolve_tag_id(cfg.ocr_tag)
    if not tag_id:
        yield SyncEvent(kind="error", detail=f"OCR tag '{cfg.ocr_tag}' not found in Paperless")
        yield SyncEvent(kind="summary", data=counts)
        return

    if docs is None:
        docs = await paperless.list_documents_by_tag(tag_id)
    else:
        docs = [d for d in docs if tag_id in (d.get("tags") or [])]
    yield SyncEvent(kind="started", detail=f"{len(docs)} document(s) tagged '{cfg.ocr_tag}'")

    for doc in docs:
        doc_id = doc["id"]
        title = doc.get("title", f"Untitled (Paperless #{doc_id})")
        if selected is not None and f"doc:{doc_id}" not in selected:
            continue
        text = _current_text(doc)
        create = _no_transcript(text)
        gid = _doc_gramps_id(doc, cfg.gramps_id_field_id)
        cols = {"transcribe": "no text yet" if create else f"replace {len(text)} chars"}
        row = dict(kind="item", entity="doc", source_id=str(doc_id), gramps_id=gid, title=title)

        if not apply:
            counts["transcribed" if create else "replaced"] += 1
            yield SyncEvent(**row, action="would_create" if create else "would_replace",
                            data={"cols": cols})
            continue

        try:
            data, mime = await paperless.download_original(doc_id)
        except Exception as exc:  # noqa: BLE001
            counts["errors"] += 1
            yield SyncEvent(**row, action="failed", detail=f"download failed: {exc}")
            continue
        if mime not in _OK_MIME:
            counts["errors"] += 1
            yield SyncEvent(**row, action="failed",
                            detail=f"unsupported file type for OCR: {mime}")
            continue

        try:
            new_text = await transcribe_document(gemini, data, mime, OCR_PROMPT,
                                                 gem_cfg.thinking_budget)
        except GeminiError as exc:
            counts["errors"] += 1
            yield SyncEvent(**row, action="failed", detail=f"Gemini: {exc}")
            continue
        if not new_text:
            counts["errors"] += 1
            yield SyncEvent(**row, action="failed", detail="Gemini returned no text")
            continue

        try:
            await paperless.patch_content(doc_id, new_text)
        except Exception as exc:  # noqa: BLE001
            counts["errors"] += 1
            yield SyncEvent(**row, action="failed", detail=f"content write-back failed: {exc}")
            continue

        cols["new text"] = f"{len(new_text)} chars"
        cur_tags = set(doc.get("tags") or [])
        tt = cfg.transcription_tag_id
        wanted = (cur_tags | ({tt} if tt else set())) - {tag_id}
        if tt:
            cols["transcription tag"] = "already set" if tt in cur_tags else "added"
        cols["OCR tag"] = "removed"
        if wanted != cur_tags:
            try:
                await paperless.patch_tags(doc_id, sorted(wanted))
            except Exception as exc:  # noqa: BLE001
                cols["tags"] = f"update failed: {exc}"

        counts["transcribed" if create else "replaced"] += 1
        yield SyncEvent(**row, action="created" if create else "replaced", data={"cols": cols})

    yield SyncEvent(kind="summary", data=counts)


async def run_with_sync(
    paperless: PaperlessClient,
    gramps,
    gemini: GeminiClient,
    cfg: SyncPaperlessConfig,
    gem_cfg: GeminiConfig,
    docs: list[dict] | None = None,
    selected: set[str] | None = None,
) -> AsyncIterator[SyncEvent]:
    """OCR, then the transcription notes of what got new text"""
    from . import sync_paperless

    counts: dict[str, int] = {}
    transcribed: list[int] = []
    async for ev in run(paperless, gemini, cfg, gem_cfg, apply=True, docs=docs, selected=selected):
        if ev.kind == "summary":
            for key, n in (ev.data or {}).items():
                counts[key] = counts.get(key, 0) + n
            continue
        if ev.kind == "item" and ev.action in ("created", "replaced") and ev.source_id:
            transcribed.append(int(ev.source_id))
        yield ev
    if transcribed:
        async for ev in sync_paperless.sync(paperless, gramps, cfg, apply=True, doc_ids=transcribed):
            if ev.kind == "summary":
                for key, n in (ev.data or {}).items():
                    counts[key] = counts.get(key, 0) + n
                continue
            if ev.kind == "started":
                continue
            yield ev
    yield SyncEvent(kind="summary", data=counts)
