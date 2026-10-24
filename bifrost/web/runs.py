from __future__ import annotations

import sqlite3
from typing import AsyncIterator

from ..core.db import now
from ..core.events import SyncEvent

ACTIVE: dict[int, dict] = {}


def sweep(conn: sqlite3.Connection) -> int:
    """Close every run a restart left 'running' as interrupted; how many there were"""
    with conn:
        cur = conn.execute(
            "UPDATE runs SET status='interrupted', finished_at=? WHERE status='running'",
            (now(),),
        )
    return cur.rowcount


async def record_run(
    conn: sqlite3.Connection, job: str, events: AsyncIterator[SyncEvent]
) -> tuple[int, list[SyncEvent]]:
    with conn:
        cur = conn.execute(
            "INSERT INTO runs (job, status, started_at) VALUES (?, 'running', ?)",
            (job, now()),
        )
        run_id = cur.lastrowid

    ACTIVE[run_id] = {"run_id": run_id, "job": job, "started_at": now()}
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
                    (run_id, seq, now(), ev.to_json()),
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
                (now(), run_id),
            )
        raise
    finally:
        ACTIVE.pop(run_id, None)

    with conn:
        conn.execute(
            "UPDATE runs SET status=?, finished_at=?, summary=? WHERE id=?",
            (status, now(), summary, run_id),
        )
    return run_id, collected
