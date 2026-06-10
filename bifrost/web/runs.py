"""Record a module operation as a run with structured events.

Phase 1 shape: drive the generator to completion, persist every event, return
them for the response. Live SSE streaming arrives with the sync module
(Phase 2) — the schema already supports it.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import AsyncIterator

from ..core.events import SyncEvent


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


async def record_run(
    conn: sqlite3.Connection, job: str, events: AsyncIterator[SyncEvent]
) -> tuple[int, list[SyncEvent]]:
    with conn:
        cur = conn.execute(
            "INSERT INTO runs (job, status, started_at) VALUES (?, 'running', ?)",
            (job, _now()),
        )
        run_id = cur.lastrowid

    collected: list[SyncEvent] = []
    status = "ok"
    summary = None
    try:
        seq = 0
        async for ev in events:
            collected.append(ev)
            with conn:
                conn.execute(
                    "INSERT INTO run_events (run_id, seq, ts, payload) VALUES (?, ?, ?, ?)",
                    (run_id, seq, _now(), ev.to_json()),
                )
            seq += 1
            if ev.kind == "summary":
                summary = ev.to_json()
            if ev.kind == "error" or ev.action == "failed":
                status = "error"
    except Exception:
        with conn:
            conn.execute(
                "UPDATE runs SET status='error', finished_at=? WHERE id=?",
                (_now(), run_id),
            )
        raise

    with conn:
        conn.execute(
            "UPDATE runs SET status=?, finished_at=?, summary=? WHERE id=?",
            (status, _now(), summary, run_id),
        )
    return run_id, collected
