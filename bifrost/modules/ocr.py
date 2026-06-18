"""Gemini OCR — transcribe a Paperless document in place.

Tag a document with the configured OCR tag; this downloads its original file,
sends it to Gemini for a faithful transcription, and writes the text straight
into the SAME Paperless document's `content` field. Same document id, so it
shows in Paperless search and flows to Gramps via the existing transcription
sync — no new documents, no broken links.

Preview is free (it only lists what would run); the Gemini call — and the
spend — happens only on apply. The ocr_state table stops a run from
re-transcribing (and re-paying) docs already done, unless force.
"""

from __future__ import annotations

import io
import sqlite3
from datetime import datetime
from typing import AsyncIterator

from pypdf import PdfReader, PdfWriter

from ..core.clients import GeminiClient, GeminiError, PaperlessClient
from ..core.config import GeminiConfig, SyncPaperlessConfig
from ..core.events import SyncEvent

OCR_PROMPT = """You are transcribing a historical or genealogical document \
image (it may be handwritten, old printed type, or a photograph of a record).

Transcribe ALL text exactly as it appears. Preserve the original spelling, \
capitalization, punctuation, diacritics, line breaks, and LANGUAGE — do not \
translate or modernize. Include both handwritten and printed text. For a \
genuinely illegible word write [illegible]; for an uncertain reading write the \
best guess followed by a question mark in brackets, e.g. Andersson[?].

Output ONLY the transcription — no preamble, no commentary, no markdown."""

# Gemini accepts these inline; anything else we send as-is and let it try.
_OK_MIME = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif",
            "application/pdf"}

# Every Gemini model caps a single response at 65,536 output tokens, so a long
# document's transcription can't fit in one call. Transcribe a multi-page PDF in
# page ranges and stitch the results. CHUNK_PAGES is the starting range; a range
# that still overflows (dense pages) is halved adaptively, down to one page.
CHUNK_PAGES = 30


def _pdf_pages(data: bytes) -> int | None:
    """Page count, or None if the bytes aren't a parseable PDF."""
    try:
        return len(PdfReader(io.BytesIO(data)).pages)
    except Exception:  # noqa: BLE001
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
    """Transcribe pages [lo, hi); on a MAX_TOKENS overflow, halve and recurse."""
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
    """Transcribe a document, chunking a multi-page PDF so no single response
    exceeds the model's output-token ceiling. Images and single-page/unparseable
    PDFs go through in one call."""
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


def _ocr_done(conn: sqlite3.Connection, doc_id: int) -> bool:
    return conn.execute(
        "SELECT 1 FROM ocr_state WHERE paperless_id = ?", (doc_id,)).fetchone() is not None


def _set_ocr(conn: sqlite3.Connection, doc_id: int, model: str, chars: int) -> None:
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO ocr_state (paperless_id, model, chars, ocr_at)"
            " VALUES (?, ?, ?, ?)",
            (doc_id, model, chars, datetime.now().isoformat(timespec="seconds")))


async def pending_count(
    paperless: PaperlessClient, conn: sqlite3.Connection, cfg: SyncPaperlessConfig
) -> int:
    if not cfg.ocr_tag:
        return 0
    tag_id = await paperless.resolve_tag_id(cfg.ocr_tag)
    if not tag_id:
        return 0
    docs = await paperless.list_documents_by_tag(tag_id)
    return sum(1 for d in docs if not _ocr_done(conn, d["id"]))


async def run(
    paperless: PaperlessClient,
    gemini: GeminiClient,
    conn: sqlite3.Connection,
    cfg: SyncPaperlessConfig,
    gem_cfg: GeminiConfig,
    apply: bool,
    force: bool = False,
    single_doc_id: int | None = None,
) -> AsyncIterator[SyncEvent]:
    counts = {"transcribed": 0, "skipped": 0, "errors": 0}

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

    docs = await paperless.list_documents_by_tag(tag_id)
    if single_doc_id is not None:
        docs = [d for d in docs if d["id"] == single_doc_id]
    yield SyncEvent(kind="started", detail=f"{len(docs)} document(s) tagged '{cfg.ocr_tag}'")

    for doc in docs:
        doc_id = doc["id"]
        title = doc.get("title", f"Untitled (Paperless #{doc_id})")
        if not force and _ocr_done(conn, doc_id):
            counts["skipped"] += 1
            continue

        cur_chars = len((doc.get("content") or "").strip())
        if not apply:
            counts["transcribed"] += 1
            yield SyncEvent(kind="item", entity="doc", action="would_update",
                            source_id=str(doc_id), title=title,
                            data={"cols": {"current text": f"{cur_chars} chars"}})
            continue

        try:
            data, mime = await paperless.download_original(doc_id)
        except Exception as exc:  # noqa: BLE001
            counts["errors"] += 1
            yield SyncEvent(kind="item", entity="doc", action="failed",
                            source_id=str(doc_id), title=title,
                            detail=f"download failed: {exc}")
            continue
        if mime not in _OK_MIME:
            counts["errors"] += 1
            yield SyncEvent(kind="item", entity="doc", action="failed",
                            source_id=str(doc_id), title=title,
                            detail=f"unsupported file type for OCR: {mime}")
            continue

        try:
            text = await transcribe_document(gemini, data, mime, OCR_PROMPT, gem_cfg.thinking_budget)
        except GeminiError as exc:
            counts["errors"] += 1
            yield SyncEvent(kind="item", entity="doc", action="failed",
                            source_id=str(doc_id), title=title, detail=f"Gemini: {exc}")
            continue
        if not text:
            counts["errors"] += 1
            yield SyncEvent(kind="item", entity="doc", action="failed",
                            source_id=str(doc_id), title=title,
                            detail="Gemini returned no text")
            continue

        try:
            await paperless.patch_content(doc_id, text)
        except Exception as exc:  # noqa: BLE001
            counts["errors"] += 1
            yield SyncEvent(kind="item", entity="doc", action="failed",
                            source_id=str(doc_id), title=title,
                            detail=f"content write-back failed: {exc}")
            continue

        _set_ocr(conn, doc_id, gem_cfg.model, len(text))
        cols = {"current text": f"{cur_chars} chars", "transcribed": f"{len(text)} chars"}

        # Stamp the transcription tag so the Gramps transcription sync turns the
        # new text into a note — no manual step. Best-effort: OCR already
        # succeeded, so a tagging hiccup is a note, not a failure.
        tt = cfg.transcription_tag_id
        if tt:
            cur_tags = doc.get("tags") or []
            if tt in cur_tags:
                cols["transcription tag"] = "already set"
            else:
                try:
                    await paperless.patch_tags(doc_id, sorted(set(cur_tags) | {tt}))
                    cols["transcription tag"] = "added"
                except Exception as exc:  # noqa: BLE001
                    cols["transcription tag"] = f"add failed: {exc}"

        counts["transcribed"] += 1
        yield SyncEvent(kind="item", entity="doc", action="updated",
                        source_id=str(doc_id), gramps_id=None, title=title,
                        data={"cols": cols})

    yield SyncEvent(kind="summary", data=counts)
