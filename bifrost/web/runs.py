"""Record a module operation as a run with structured events
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import AsyncIterator

from ..core.events import SyncEvent


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# Live progress of in-flight runs, keyed by run id. "progress" events land
# here for pollers (/api/runs/active) and nowhere else — they are never
# written to run_events nor returned with the finished run. Single-process
# app, so a module dict is the whole registry.
ACTIVE: dict[int, dict] = {}


async def record_run(
    conn: sqlite3.Connection, job: str, events: AsyncIterator[SyncEvent]
) -> tuple[int, list[SyncEvent]]:
    with conn:
        cur = conn.execute(
            "INSERT INTO runs (job, status, started_at) VALUES (?, 'running', ?)",
            (job, _now()),
        )
        run_id = cur.lastrowid

    ACTIVE[run_id] = {"run_id": run_id, "job": job, "started_at": _now()}
    collected: list[SyncEvent] = []
    status = "ok"
    summary = None
    try:
        seq = 0
        async for ev in events:
            if ev.kind == "progress":
                ACTIVE[run_id].update({"detail": ev.detail, **(ev.data or {})})
                continue
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
    finally:
        ACTIVE.pop(run_id, None)

    with conn:
        conn.execute(
            "UPDATE runs SET status=?, finished_at=?, summary=? WHERE id=?",
            (status, _now(), summary, run_id),
        )
    return run_id, collected
