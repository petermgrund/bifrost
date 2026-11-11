from __future__ import annotations

import itertools
import logging
from datetime import datetime, timezone
from typing import AsyncIterator

from ..core.events import SyncEvent

log = logging.getLogger("bifrost.runs")

ACTIVE: dict[int, dict] = {}
_run_ids = itertools.count(1)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def record_run(job: str, events: AsyncIterator[SyncEvent]) -> tuple[int, list[SyncEvent]]:
    """Collect a scan's events, publishing its progress while it runs"""
    run_id = next(_run_ids)
    ACTIVE[run_id] = {"run_id": run_id, "job": job, "started_at": _now()}
    collected: list[SyncEvent] = []
    try:
        async for ev in events:
            if ev.kind == "progress":
                ACTIVE[run_id].update({"detail": ev.detail, **(ev.data or {})})
                continue
            collected.append(ev)
    except Exception:
        log.exception("%s failed", job)
        raise
    finally:
        ACTIVE.pop(run_id, None)
    summary = next((e.data for e in collected if e.kind == "summary"), None)
    failed = [e for e in collected if e.kind == "error" or e.action == "failed"]
    log.info("%s: %s%s", job, summary or "done", f", {len(failed)} failed" if failed else "")
    for e in failed:
        log.warning("%s: %s %s", job, e.gramps_id or e.source_id or "", e.detail)
    return run_id, collected
