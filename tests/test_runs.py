import asyncio

import pytest

from bifrost.core import db
from bifrost.core.events import SyncEvent
from bifrost.web import runs


def test_progress_events_are_transient(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    snapshots = []

    async def events():
        yield SyncEvent(kind="started", detail="2 docs")
        yield SyncEvent(kind="progress", detail="Checking new documents",
                        data={"done": 1, "total": 2})
        snapshots.append({k: dict(v) for k, v in runs.ACTIVE.items()})
        yield SyncEvent(kind="item", entity="doc", action="would_create", source_id="1")
        yield SyncEvent(kind="summary", data={"created": 1})

    run_id, collected = asyncio.run(
        runs.record_run(conn, "sync.paperless.preview", events()))

    live = snapshots[0][run_id]
    assert live["job"] == "sync.paperless.preview"
    assert live["done"] == 1 and live["total"] == 2
    assert live["detail"] == "Checking new documents"
    assert run_id not in runs.ACTIVE

    assert [e.kind for e in collected] == ["started", "item", "summary"]
    stored = conn.execute(
        "SELECT payload FROM run_events WHERE run_id=?", (run_id,)).fetchall()
    assert len(stored) == 3
    assert all('"progress"' not in r["payload"] for r in stored)


def test_active_cleared_when_generator_raises(tmp_path):
    conn = db.connect(tmp_path / "e.db")

    async def boom():
        yield SyncEvent(kind="progress", data={"done": 0, "total": 5})
        raise RuntimeError("kaput")

    with pytest.raises(RuntimeError):
        asyncio.run(runs.record_run(conn, "sync.paperless", boom()))

    assert not runs.ACTIVE
    assert conn.execute("SELECT status FROM runs").fetchone()["status"] == "error"
