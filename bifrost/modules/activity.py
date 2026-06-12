"""Activity — weekly productivity aggregation over the Gramps transaction log.

Counts DISTINCT objects per week × action × object class: an object edited five
times in a week counts once, and an object added that week doesn't also count
as edited (the edits are part of creating it). Undo transactions and
reference-map rows (ref_handle set, numeric obj_class) are skipped.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from ..core.clients import GrampsClient

ACTIONS = {0: "added", 1: "edited", 2: "deleted"}
CLASSES = ["Person", "Family", "Event", "Place",
           "Citation", "Source", "Note", "Media"]


async def weekly(gramps: GrampsClient) -> dict:
    txns = await gramps.list_transaction_history()
    # week start (Monday) -> action -> class -> distinct handles
    buckets: dict[str, dict[str, dict[str, set]]] = {}
    for txn in txns:
        if txn.get("undo"):
            continue
        ts = txn.get("timestamp") or (txn.get("connection") or {}).get("timestamp")
        if not ts:
            continue
        day = datetime.fromtimestamp(ts).date()
        week = (day - timedelta(days=day.weekday())).isoformat()
        for ch in txn.get("changes") or []:
            if ch.get("ref_handle"):           # reference-map bookkeeping row
                continue
            action = ACTIONS.get(ch.get("trans_type"))
            cls = ch.get("obj_class")
            if not action or not isinstance(cls, str):
                continue
            if cls not in CLASSES:
                cls = "Other"
            (buckets.setdefault(week, {})
                    .setdefault(action, {})
                    .setdefault(cls, set())
                    .add(ch.get("obj_handle")))

    weeks = []
    for week in sorted(buckets, reverse=True):
        by_action = buckets[week]
        added = by_action.get("added", {})
        actions: dict[str, dict[str, int]] = {}
        for action, classes in by_action.items():
            counts = {}
            for cls, handles in classes.items():
                if action == "edited":          # creating-week edits aren't edits
                    handles = handles - added.get(cls, set())
                if handles:
                    counts[cls] = len(handles)
            if counts:
                counts["total"] = sum(counts.values())
                actions[action] = counts
        if actions:
            weeks.append({"week": week, "actions": actions})
    return {"classes": CLASSES + ["Other"], "weeks": weeks}
