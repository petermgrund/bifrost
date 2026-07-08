"""Unit tests for the PDF width-normalization logic (modules/reprocess.py)."""

import asyncio
import io

from pypdf import PdfReader, PdfWriter

from bifrost.modules.reprocess import (
    MODE_NARROWEST,
    MODE_WIDEST,
    TOLERANCE_PT,
    effective_size,
    plan_pages,
    rebuild,
    run,
    run_batch,
    scan_mixed_widths,
)


def _pdf(*sizes, rotations=None) -> bytes:
    w = PdfWriter()
    for i, (pw, ph) in enumerate(sizes):
        page = w.add_blank_page(pw, ph)
        if rotations and rotations[i]:
            page.rotation = rotations[i]
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# plan / rebuild
# ---------------------------------------------------------------------------

def test_plan_widest():
    plan = plan_pages(_pdf((612, 792), (495, 700)), MODE_WIDEST)
    assert [p["factor"] for p in plan] == [1.0, 612 / 495]
    assert plan[1]["width"] == 495 and plan[1]["height"] == 700


def test_plan_narrowest():
    plan = plan_pages(_pdf((612, 792), (495, 700)), MODE_NARROWEST)
    assert [p["factor"] for p in plan] == [495 / 612, 1.0]


def test_plan_uses_displayed_width_for_rotated_pages():
    # a 612×792 page rotated 90° displays 792 wide — it IS the widest page
    plan = plan_pages(_pdf((612, 792), (612, 792), rotations=[0, 90]), MODE_WIDEST)
    assert plan[1]["factor"] == 1.0
    assert plan[0]["factor"] == 792 / 612


def test_plan_tolerance_skips_near_target_pages():
    plan = plan_pages(_pdf((612, 792), (612 - TOLERANCE_PT / 2, 792)), MODE_WIDEST)
    assert all(p["factor"] == 1.0 for p in plan)


def test_plan_rejects_garbage():
    try:
        plan_pages(b"not a pdf", MODE_WIDEST)
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_rebuild_equalizes_widths_and_keeps_aspect():
    data = _pdf((612, 792), (495, 700), (300, 300))
    out = rebuild(data, plan_pages(data, MODE_WIDEST))
    pages = PdfReader(io.BytesIO(out)).pages
    sizes = [effective_size(p) for p in pages]
    assert all(abs(w - 612) < 0.01 for w, _ in sizes)
    # aspect ratios preserved
    assert abs(sizes[1][1] - 700 * (612 / 495)) < 0.01
    assert abs(sizes[2][1] - 300 * (612 / 300)) < 0.01


# ---------------------------------------------------------------------------
# the run generator, against a fake Paperless client
# ---------------------------------------------------------------------------

class FakePaperless:
    def __init__(self, docs):  # {doc_id: (bytes, mime)}
        self._docs = docs
        self.uploads = []
        self.task_polls = 0

    async def get_document(self, doc_id):
        return {"id": doc_id, "title": f"Doc {doc_id}",
                "original_file_name": f"doc{doc_id}.pdf"}

    async def download_original(self, doc_id):
        return self._docs[doc_id]

    async def update_version(self, doc_id, data, filename, version_label=None):
        self.uploads.append({"doc_id": doc_id, "data": data, "filename": filename,
                             "label": version_label})
        return f"task-{doc_id}"

    async def task_status(self, task_uuid):
        self.task_polls += 1
        return {"status": "SUCCESS"}

    async def resolve_tag_id(self, name):
        return 42 if name == "doc" else None

    async def list_documents_by_tag(self, tag_id):
        return [{"id": i, "title": f"Doc {i}", "mime_type": m, "page_count": None}
                for i, (_, m) in self._docs.items()]


def _events(gen):
    async def collect():
        return [e async for e in gen]
    return asyncio.run(collect())


def _summary(events):
    return next(e.data for e in events if e.kind == "summary")


def test_run_preview_measures_without_uploading():
    fake = FakePaperless({7: (_pdf((612, 792), (495, 700)), "application/pdf")})
    events = _events(run(fake, 7, MODE_WIDEST, apply=False))
    assert fake.uploads == []
    assert _summary(events) == {"pages_scaled": 1, "skipped": 1, "uploaded": 1, "errors": 0}
    pages = [e for e in events if e.entity == "page"]
    assert [e.action for e in pages] == ["skipped", "would_update"]
    assert "612 × 792" in pages[0].data["cols"]["size"]


def test_run_apply_uploads_normalized_version():
    fake = FakePaperless({7: (_pdf((612, 792), (495, 700)), "application/pdf")})
    events = _events(run(fake, 7, MODE_NARROWEST, apply=True))
    assert len(fake.uploads) == 1
    assert fake.uploads[0]["filename"] == "doc7.pdf"
    assert fake.uploads[0]["label"] == "width-normalized (narrowest)"
    sizes = [effective_size(p)
             for p in PdfReader(io.BytesIO(fake.uploads[0]["data"])).pages]
    assert all(abs(w - 495) < 0.01 for w, _ in sizes)
    assert _summary(events)["uploaded"] == 1
    done = next(e for e in events if e.entity == "doc" and e.action == "updated")
    assert "consumed" in done.detail


def test_run_no_wait_skips_consume_polling():
    fake = FakePaperless({7: (_pdf((612, 792), (495, 700)), "application/pdf")})
    events = _events(run(fake, 7, MODE_WIDEST, apply=True, wait_consume=False))
    assert len(fake.uploads) == 1
    assert fake.task_polls == 0
    done = next(e for e in events if e.entity == "doc" and e.action == "updated")
    assert "background" in done.detail


def test_run_uniform_pdf_uploads_nothing():
    fake = FakePaperless({7: (_pdf((612, 792), (612, 792)), "application/pdf")})
    events = _events(run(fake, 7, MODE_WIDEST, apply=True))
    assert fake.uploads == []
    assert _summary(events)["uploaded"] == 0
    skip = next(e for e in events if e.entity == "doc" and e.action == "skipped")
    assert "already share width" in skip.detail


def test_run_rejects_non_pdf():
    fake = FakePaperless({7: (b"\xff\xd8jpeg", "image/jpeg")})
    events = _events(run(fake, 7, MODE_WIDEST, apply=True))
    assert fake.uploads == []
    assert _summary(events)["errors"] == 1
    failed = next(e for e in events if e.action == "failed")
    assert "not a PDF" in failed.detail


def test_run_rejects_unknown_mode():
    fake = FakePaperless({7: (_pdf((612, 792)), "application/pdf")})
    events = _events(run(fake, 7, "sideways", apply=False))
    assert _summary(events)["errors"] == 1


# ---------------------------------------------------------------------------
# scan + batch
# ---------------------------------------------------------------------------

def test_scan_finds_only_mixed_width_multipage_pdfs():
    fake = FakePaperless({
        1: (_pdf((612, 792), (495, 700)), "application/pdf"),   # mixed → row
        2: (_pdf((612, 792), (612, 792)), "application/pdf"),   # uniform
        3: (_pdf((612, 792)), "application/pdf"),               # single page
        4: (b"\xff\xd8jpeg", "image/jpeg"),                     # not a PDF
    })
    result = asyncio.run(scan_mixed_widths(fake, "doc"))
    assert result["tagged"] == 4
    assert result["candidates"] == 3  # the jpeg is excluded up front
    assert result["errors"] == []
    assert [r["doc_id"] for r in result["rows"]] == [1]
    row = result["rows"][0]
    assert row["pages"] == 2
    assert row["widths"] == [495, 612]
    assert (row["min_width"], row["max_width"]) == (495, 612)


def test_scan_unknown_tag_raises():
    fake = FakePaperless({})
    try:
        asyncio.run(scan_mixed_widths(fake, "nope"))
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_run_batch_merges_summaries_and_suppresses_page_events():
    fake = FakePaperless({
        1: (_pdf((612, 792), (495, 700)), "application/pdf"),   # mixed
        2: (_pdf((612, 792), (612, 792)), "application/pdf"),   # uniform
    })
    events = _events(run_batch(fake, [1, 2], MODE_WIDEST))
    assert [u["doc_id"] for u in fake.uploads] == [1]
    assert fake.task_polls == 0  # batch never waits on consume
    assert not any(e.entity == "page" or e.kind == "started" for e in events)
    assert _summary(events) == {"pages_scaled": 1, "skipped": 3, "uploaded": 1, "errors": 0}
    outcomes = {e.source_id: e.action for e in events if e.entity == "doc"}
    assert outcomes == {"1": "updated", "2": "skipped"}
    assert sum(1 for e in events if e.kind == "summary") == 1
