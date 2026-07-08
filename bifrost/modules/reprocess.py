"""Reprocess — rebuild a Paperless document's PDF so every page shares one width.

Scanned multi-page documents often mix page sizes (folded letters, odd
enclosures, a verso scanned at another resolution), so viewers zoom-jump
between pages. This downloads the document's current original file, scales
every PDF page to a common width — the widest or the narrowest page in the
file, aspect ratio preserved — and uploads the result as a NEW VERSION of the
SAME Paperless document. Nothing is destroyed: the previous file stays in the
document's version history, and the Gramps media repoints to the new file on
the next versions-only sync (the 10-minute cron).

Preview downloads and measures only; the upload happens on apply.
"""

from __future__ import annotations

import asyncio
import io
from typing import AsyncIterator

from pypdf import PdfReader, PdfWriter

from ..core.clients import PaperlessClient
from ..core.events import SyncEvent

MODE_WIDEST = "widest"
MODE_NARROWEST = "narrowest"

# Pages already within this of the target width stay byte-identical instead of
# being scaled by ~1.0000 (scan widths jitter by fractions of a point).
TOLERANCE_PT = 1.0

# Parallel downloads during a library scan — friendly to Paperless, still ~4×
# faster than serial over the LAN.
SCAN_CONCURRENCY = 4

# How long apply waits for Paperless to consume the uploaded version before
# reporting it as merely queued (consume re-runs OCR, so big scans are slow).
CONSUME_TIMEOUT_S = 90.0
CONSUME_POLL_S = 2.0


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def effective_size(page) -> tuple[float, float]:
    """Displayed (width, height) in points — a /Rotate 90/270 page shows its
    mediabox sideways."""
    w, h = float(page.mediabox.width), float(page.mediabox.height)
    return (h, w) if page.rotation % 180 == 90 else (w, h)


def plan_pages(data: bytes, mode: str) -> list[dict]:
    """Measure every page and compute its scale factor toward the target width:
    [{page, width, height, factor}], factor 1.0 for pages already there.
    Raises ValueError when the bytes aren't a readable, unencrypted PDF."""
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ValueError("PDF is encrypted")
        sizes = [effective_size(p) for p in reader.pages]
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001 — pypdf raises many parse errors
        raise ValueError(f"not a readable PDF: {exc}") from exc
    if not sizes:
        raise ValueError("PDF has no pages")

    widths = [w for w, _ in sizes]
    target = max(widths) if mode == MODE_WIDEST else min(widths)
    return [
        {"page": i + 1, "width": w, "height": h,
         "factor": 1.0 if abs(w - target) <= TOLERANCE_PT else target / w}
        for i, (w, h) in enumerate(sizes)
    ]


def rebuild(data: bytes, plan: list[dict]) -> bytes:
    """Apply the plan's scale factors (uniform, so aspect ratio holds — pypdf
    scales content, boxes, and annotations together) and serialize."""
    reader = PdfReader(io.BytesIO(data))
    writer = PdfWriter()
    for entry, page in zip(plan, reader.pages):
        if entry["factor"] != 1.0:
            page.scale_by(entry["factor"])
        writer.add_page(page)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _fmt_size(w: float, h: float) -> str:
    return f"{w:.0f} × {h:.0f} pt"


# ---------------------------------------------------------------------------
# The run generator (preview and apply, per the house apply flag)
# ---------------------------------------------------------------------------

async def _consume_status(paperless: PaperlessClient, task_id: str) -> dict | None:
    """Poll the consume task until it settles or the timeout passes (None)."""
    loop = asyncio.get_event_loop()
    deadline = loop.time() + CONSUME_TIMEOUT_S
    while loop.time() < deadline:
        try:
            task = await paperless.task_status(task_id)
        except Exception:  # noqa: BLE001 — polling is best-effort
            task = None
        if task and task.get("status") in ("SUCCESS", "FAILURE"):
            return task
        await asyncio.sleep(CONSUME_POLL_S)
    return None


async def run(
    paperless: PaperlessClient,
    doc_id: int,
    mode: str,
    apply: bool,
    wait_consume: bool = True,
) -> AsyncIterator[SyncEvent]:
    counts = {"pages_scaled": 0, "skipped": 0, "uploaded": 0, "errors": 0}

    if mode not in (MODE_WIDEST, MODE_NARROWEST):
        counts["errors"] += 1
        yield SyncEvent(kind="error", detail=f"unknown mode {mode!r}")
        yield SyncEvent(kind="summary", data=counts)
        return

    try:
        doc = await paperless.get_document(doc_id)
        data, mime = await paperless.download_original(doc_id)
    except Exception as exc:  # noqa: BLE001
        counts["errors"] += 1
        yield SyncEvent(kind="error", source_id=str(doc_id),
                        detail=f"fetch failed: {exc}")
        yield SyncEvent(kind="summary", data=counts)
        return
    title = doc.get("title", f"Untitled (Paperless #{doc_id})")

    if mime != "application/pdf":
        counts["errors"] += 1
        yield SyncEvent(kind="item", entity="doc", action="failed",
                        source_id=str(doc_id), title=title,
                        detail=f"the document's file is {mime}, not a PDF")
        yield SyncEvent(kind="summary", data=counts)
        return

    try:
        plan = plan_pages(data, mode)
    except ValueError as exc:
        counts["errors"] += 1
        yield SyncEvent(kind="item", entity="doc", action="failed",
                        source_id=str(doc_id), title=title, detail=str(exc))
        yield SyncEvent(kind="summary", data=counts)
        return

    widths = [p["width"] for p in plan]
    target = max(widths) if mode == MODE_WIDEST else min(widths)
    yield SyncEvent(
        kind="started", source_id=str(doc_id), title=title,
        detail=(f"{len(plan)} page(s), widths {min(widths):.0f}–{max(widths):.0f} pt"
                f" → all to {target:.0f} pt ({mode} page)"))

    for p in plan:
        scaled = p["factor"] != 1.0
        counts["pages_scaled" if scaled else "skipped"] += 1
        yield SyncEvent(
            kind="item", entity="page",
            action=("updated" if apply else "would_update") if scaled else "skipped",
            source_id=str(doc_id), title=f"page {p['page']}",
            data={"cols": {
                "size": _fmt_size(p["width"], p["height"]),
                "result": (f"× {p['factor']:.3f} → "
                           f"{_fmt_size(p['width'] * p['factor'], p['height'] * p['factor'])}"
                           if scaled else "n/a"),
            }})

    if not counts["pages_scaled"]:
        yield SyncEvent(kind="item", entity="doc", action="skipped",
                        source_id=str(doc_id), title=title,
                        detail="all pages already share width")
        yield SyncEvent(kind="summary", data=counts)
        return

    if not apply:
        counts["uploaded"] = 1  # what apply would do
        yield SyncEvent(kind="summary", data=counts)
        return

    label = f"width-normalized ({mode})"
    filename = doc.get("original_file_name") or f"paperless-{doc_id}.pdf"
    if not filename.lower().endswith(".pdf"):
        # the SELECTED version is a PDF (mime-checked above) even when the
        # root document — whose name this is — was uploaded as something else
        filename = f"{filename.rsplit('.', 1)[0]}.pdf"
    try:
        new_data = rebuild(data, plan)
        task_id = await paperless.update_version(doc_id, new_data, filename, label)
    except Exception as exc:  # noqa: BLE001
        counts["errors"] += 1
        yield SyncEvent(kind="item", entity="doc", action="failed",
                        source_id=str(doc_id), title=title,
                        detail=f"version upload failed: {exc}")
        yield SyncEvent(kind="summary", data=counts)
        return

    task = await _consume_status(paperless, task_id) if wait_consume else None
    status = (task or {}).get("status")
    if status == "FAILURE":
        counts["errors"] += 1
        yield SyncEvent(kind="item", entity="doc", action="failed",
                        source_id=str(doc_id), title=title,
                        detail=("Paperless rejected the new version: "
                                f"{(task or {}).get('result') or 'unknown error'}"))
    else:
        counts["uploaded"] = 1
        if status == "SUCCESS":
            detail = f"'{label}' consumed"
        elif wait_consume:
            detail = (f"'{label}' uploaded, Paperless still"
                      f"consuming it")
        else:
            detail = f"'{label}' uploaded, consuming in background"
        yield SyncEvent(kind="item", entity="doc", action="updated",
                        source_id=str(doc_id), title=title, detail=detail,
                        data={"cols": {"pages scaled": str(counts["pages_scaled"]),
                                       "version label": label}})
    yield SyncEvent(kind="summary", data=counts)


# ---------------------------------------------------------------------------
# Library scan + batch
# ---------------------------------------------------------------------------

async def scan_mixed_widths(paperless: PaperlessClient, tag_name: str) -> dict:
    """Find every multi-page PDF under the tag whose pages have differing
    widths. A pure query — each candidate's file is downloaded and measured,
    nothing is written. Raises ValueError when the tag doesn't exist."""
    tag_id = await paperless.resolve_tag_id(tag_name)
    if tag_id is None:
        raise ValueError(f"tag '{tag_name}' not found in Paperless")
    docs = await paperless.list_documents_by_tag(tag_id)
    candidates = [
        d for d in docs
        if d.get("mime_type") == "application/pdf"
        # page_count is often null — unknown still needs measuring
        and (d.get("page_count") or 2) > 1
    ]

    sem = asyncio.Semaphore(SCAN_CONCURRENCY)

    async def measure(doc: dict) -> dict | None:
        title = doc.get("title", f"Untitled (Paperless #{doc['id']})")
        async with sem:
            try:
                data, mime = await paperless.download_original(doc["id"])
            except Exception as exc:  # noqa: BLE001
                return {"doc_id": doc["id"], "title": title,
                        "error": f"download failed: {exc}"}
        if mime != "application/pdf":
            return None  # the selected version isn't a PDF after all
        try:
            plan = plan_pages(data, MODE_WIDEST)
        except ValueError as exc:
            return {"doc_id": doc["id"], "title": title, "error": str(exc)}
        widths = [p["width"] for p in plan]
        if len(plan) < 2 or max(widths) - min(widths) <= TOLERANCE_PT:
            return None
        return {"doc_id": doc["id"], "title": title, "pages": len(plan),
                "widths": sorted({round(w) for w in widths}),
                "min_width": round(min(widths)), "max_width": round(max(widths))}

    measured = await asyncio.gather(*(measure(d) for d in candidates))
    rows = sorted((m for m in measured if m and "error" not in m),
                  key=lambda r: r["doc_id"], reverse=True)
    errors = [m for m in measured if m and "error" in m]
    return {"tag": tag_name, "tagged": len(docs), "candidates": len(candidates),
            "rows": rows, "errors": errors}


async def run_batch(
    paperless: PaperlessClient, doc_ids: list[int], mode: str,
) -> AsyncIterator[SyncEvent]:
    """Normalize a batch of documents as ONE run. Uploads don't wait for
    Paperless to consume each version (the queue drains in the background),
    and per-page/started events are suppressed — at batch scale only the
    per-document outcome matters."""
    totals = {"pages_scaled": 0, "skipped": 0, "uploaded": 0, "errors": 0}
    for doc_id in doc_ids:
        async for ev in run(paperless, doc_id, mode, apply=True, wait_consume=False):
            if ev.kind == "summary":
                for key, n in (ev.data or {}).items():
                    totals[key] = totals.get(key, 0) + n
            elif ev.kind != "started" and ev.entity != "page":
                yield ev
    yield SyncEvent(kind="summary", data=totals)
