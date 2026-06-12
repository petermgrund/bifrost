"""Activity — weekly productivity + citation-coverage from the Gramps transaction log.

Productivity counts DISTINCT objects per week × action × object class: an object
edited five times in a week counts once, and an object added that week doesn't
also count as edited (the edits are part of creating it). Undo transactions and
reference-map rows (ref_handle set, numeric obj_class) are skipped.

Citation coverage replays the log's Event payloads chronologically to compute,
at the end of each week, what share of events lacked a citation. Events that
predate the log (the January import bypassed it) are seeded from the old_data
of their first logged change — or their current state if never touched since.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from ..core.clients import GrampsClient

ACTIONS = {0: "added", 1: "edited", 2: "deleted"}
CLASSES = ["Person", "Family", "Event", "Place",
           "Citation", "Source", "Note", "Media"]


def _week_of(ts: float) -> str:
    day = datetime.fromtimestamp(ts).date()
    return (day - timedelta(days=day.weekday())).isoformat()


def _txn_ts(txn: dict) -> float | None:
    return txn.get("timestamp") or (txn.get("connection") or {}).get("timestamp")


async def dashboard(gramps: GrampsClient) -> dict:
    txns = await gramps.list_transaction_history(payloads=True)
    txns.sort(key=lambda t: t.get("id") or 0)
    events_now = await gramps.list_events_min()
    return {
        "classes": CLASSES + ["Other"],
        "weeks": _weekly_counts(txns),
        "coverage": _event_coverage(txns, events_now),
    }


def _weekly_counts(txns: list[dict]) -> list[dict]:
    # week start (Monday) -> action -> class -> distinct handles
    buckets: dict[str, dict[str, dict[str, set]]] = {}
    for txn in txns:
        if txn.get("undo"):
            continue
        ts = _txn_ts(txn)
        if not ts:
            continue
        week = _week_of(ts)
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
    return weeks


def _event_changes(txn: dict):
    for ch in txn.get("changes") or []:
        if not ch.get("ref_handle") and ch.get("obj_class") == "Event":
            yield ch


def _event_coverage(txns: list[dict], events_now: list[dict]) -> list[dict]:
    """[{week, total, uncited, pct}] — end-of-week snapshots, gap weeks carried
    forward to the current week."""
    added_in_log = {ch["obj_handle"] for t in txns for ch in _event_changes(t)
                    if ch.get("trans_type") == 0}
    # Seed pre-log events: state just before their first logged change…
    state: dict[str, bool] = {}
    for t in txns:
        for ch in _event_changes(t):
            h = ch["obj_handle"]
            if h in added_in_log or h in state:
                continue
            state[h] = bool((ch.get("old_data") or {}).get("citation_list"))
    # …or their current state if the log never touched them.
    for e in events_now:
        if e["handle"] not in added_in_log and e["handle"] not in state:
            state[e["handle"]] = bool(e.get("citation_list"))

    snaps: dict[str, tuple[int, int]] = {}

    def snap(week: str) -> None:
        snaps[week] = (len(state), sum(1 for cited in state.values() if not cited))

    cur_week = None
    for t in txns:                              # undo txns included — they change state
        ts = _txn_ts(t)
        if not ts:
            continue
        week = _week_of(ts)
        if cur_week is None:
            cur_week = week
        elif week != cur_week:
            snap(cur_week)
            cur_week = week
        for ch in _event_changes(t):
            h, tt = ch["obj_handle"], ch.get("trans_type")
            if tt in (0, 1):
                state[h] = bool((ch.get("new_data") or {}).get("citation_list"))
            elif tt == 2:
                state.pop(h, None)
    if cur_week:
        snap(cur_week)

    out: list[dict] = []
    if snaps:
        today = date.today()
        last_monday = (today - timedelta(days=today.weekday())).isoformat()
        wk = datetime.strptime(min(snaps), "%Y-%m-%d").date()
        latest: tuple[int, int] | None = None
        while True:
            iso = wk.isoformat()
            latest = snaps.get(iso, latest)
            if latest:
                total, uncited = latest
                out.append({"week": iso, "total": total, "uncited": uncited,
                            "pct": round(100 * uncited / total) if total else 0})
            if iso >= last_monday:
                break
            wk += timedelta(days=7)
    return out
