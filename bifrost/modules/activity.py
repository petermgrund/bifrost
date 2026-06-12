"""Activity — weekly productivity + citation-coverage from the Gramps transaction log.

Productivity counts DISTINCT objects per week × action × object class: an object
edited five times in a week counts once, and an object added that week doesn't
also count as edited (the edits are part of creating it). Undo transactions and
reference-map rows (ref_handle set, numeric obj_class) are skipped.

Citation coverage replays the log's Event payloads chronologically to compute,
at the end of each week, how many events had 0 / 1 / 2+ citations. Events that
predate the log (the January import bypassed it) are seeded from the old_data
of their first logged change — or their current state if never touched since.

Everything before START_WEEK (the first full week of the tree's life on Gramps
Web) is dropped from the output; the replay still processes earlier transactions
so state stays correct.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from ..core.clients import GrampsClient

ACTIONS = {0: "added", 1: "edited", 2: "deleted"}
CLASSES = ["Person", "Family", "Event", "Place",
           "Citation", "Source", "Note", "Media"]
START_WEEK = "2026-01-05"
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Gramps EventType enum — raw log payloads carry only the value for standard
# types (string is set only for custom types).
EVENT_TYPES = {
    1: "Marriage", 2: "Marriage Settlement", 3: "Marriage License",
    4: "Marriage Contract", 5: "Marriage Banns", 6: "Engagement",
    7: "Divorce", 8: "Divorce Filing", 9: "Annulment", 10: "Alternate Marriage",
    11: "Adopted", 12: "Birth", 13: "Death", 14: "Adult Christening",
    15: "Baptism", 16: "Bar Mitzvah", 17: "Bat Mitzvah", 18: "Blessing",
    19: "Burial", 20: "Cause Of Death", 21: "Census", 22: "Christening",
    23: "Confirmation", 24: "Cremation", 25: "Degree", 26: "Education",
    27: "Elected", 28: "Emigration", 29: "First Communion", 30: "Immigration",
    31: "Graduation", 32: "Medical Information", 33: "Military Service",
    34: "Naturalization", 35: "Nobility Title", 36: "Number of Marriages",
    37: "Occupation", 38: "Ordination", 39: "Probate", 40: "Property",
    41: "Religion", 42: "Residence", 43: "Retirement", 44: "Will",
}


def _week_of(ts: float) -> str:
    day = datetime.fromtimestamp(ts).date()
    return (day - timedelta(days=day.weekday())).isoformat()


def _txn_ts(txn: dict) -> float | None:
    return txn.get("timestamp") or (txn.get("connection") or {}).get("timestamp")


def current_week() -> str:
    today = date.today()
    return (today - timedelta(days=today.weekday())).isoformat()


OBJ_ENDPOINTS = {"Person": "/people/", "Family": "/families/", "Event": "/events/",
                 "Place": "/places/", "Citation": "/citations/", "Source": "/sources/",
                 "Note": "/notes/", "Media": "/media/"}


async def dashboard(gramps: GrampsClient) -> dict:
    txns = await gramps.list_transaction_history(payloads=True)
    txns.sort(key=lambda t: t.get("id") or 0)
    events_now = await gramps.list_events_min()
    current = {cls: await gramps.list_handles(ep) for cls, ep in OBJ_ENDPOINTS.items()}
    return {
        "classes": CLASSES + ["Other"],
        "weeks": _weekly_counts(txns),
        "coverage": _event_coverage(txns, events_now),
        "totals": _db_totals(txns, current),
        "this_week": _week_detail(txns, current_week()),
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
        if week < START_WEEK:
            continue
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


def _n_citations(data: dict | None) -> int:
    return len((data or {}).get("citation_list") or [])


def _event_coverage(txns: list[dict], events_now: list[dict]) -> list[dict]:
    """[{week, total, c0, c1, c2}] — end-of-week snapshots of how many events
    had 0 / 1 / 2+ citations; gap weeks carried forward to the current week."""
    added_in_log = {ch["obj_handle"] for t in txns for ch in _event_changes(t)
                    if ch.get("trans_type") == 0}
    # Seed pre-log events: state just before their first logged change…
    state: dict[str, int] = {}
    for t in txns:
        for ch in _event_changes(t):
            h = ch["obj_handle"]
            if h in added_in_log or h in state:
                continue
            state[h] = _n_citations(ch.get("old_data"))
    # …or their current state if the log never touched them.
    for e in events_now:
        if e["handle"] not in added_in_log and e["handle"] not in state:
            state[e["handle"]] = _n_citations(e)

    snaps: dict[str, tuple[int, int, int, int]] = {}

    def snap(week: str) -> None:
        c0 = sum(1 for n in state.values() if n == 0)
        c1 = sum(1 for n in state.values() if n == 1)
        snaps[week] = (len(state), c0, c1, len(state) - c0 - c1)

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
                state[h] = _n_citations(ch.get("new_data"))
            elif tt == 2:
                state.pop(h, None)
    if cur_week:
        snap(cur_week)

    out: list[dict] = []
    if snaps:
        last_monday = current_week()
        wk = datetime.strptime(min(snaps), "%Y-%m-%d").date()
        latest: tuple[int, int, int, int] | None = None
        while True:
            iso = wk.isoformat()
            latest = snaps.get(iso, latest)
            if latest and iso >= START_WEEK:
                total, c0, c1, c2 = latest
                out.append({"week": iso, "total": total, "c0": c0, "c1": c1, "c2": c2})
            if iso >= last_monday:
                break
            wk += timedelta(days=7)
    return out


def _db_totals(txns: list[dict], current: dict[str, set]) -> list[dict]:
    """[{week, counts: {cls: n}}] — how many objects of each class existed in
    the database at the end of each week, reconstructed from the log.

    Pre-log population per class: current objects never logged as added, plus
    objects whose first log appearance is an update or delete."""
    added_in_log: dict[str, set] = {cls: set() for cls in OBJ_ENDPOINTS}
    state: dict[str, set] = {cls: set() for cls in OBJ_ENDPOINTS}
    for t in txns:
        for ch in t.get("changes") or []:
            cls = ch.get("obj_class")
            if ch.get("ref_handle") or cls not in OBJ_ENDPOINTS:
                continue
            h = ch.get("obj_handle")
            if ch.get("trans_type") == 0:
                added_in_log[cls].add(h)
            elif h not in added_in_log[cls]:    # first seen as update/delete → pre-log
                state[cls].add(h)
    for cls, handles in current.items():
        state[cls] |= handles - added_in_log[cls]

    snaps: dict[str, dict[str, int]] = {}
    cur_week = None
    for t in txns:                              # undo txns included — they change state
        ts = _txn_ts(t)
        if not ts:
            continue
        week = _week_of(ts)
        if cur_week is None:
            cur_week = week
        elif week != cur_week:
            snaps[cur_week] = {cls: len(s) for cls, s in state.items()}
            cur_week = week
        for ch in t.get("changes") or []:
            cls = ch.get("obj_class")
            if ch.get("ref_handle") or cls not in OBJ_ENDPOINTS:
                continue
            h, tt = ch.get("obj_handle"), ch.get("trans_type")
            if tt in (0, 1):
                state[cls].add(h)
            elif tt == 2:
                state[cls].discard(h)
    if cur_week:
        snaps[cur_week] = {cls: len(s) for cls, s in state.items()}

    out: list[dict] = []
    if snaps:
        last_monday = current_week()
        wk = datetime.strptime(min(snaps), "%Y-%m-%d").date()
        latest: dict[str, int] | None = None
        while True:
            iso = wk.isoformat()
            latest = snaps.get(iso, latest)
            if latest and iso >= START_WEEK:
                out.append({"week": iso, "counts": latest})
            if iso >= last_monday:
                break
            wk += timedelta(days=7)
    return out


def _label(cls: str, d: dict) -> str:
    """Best-effort human label for an object from its log payload."""
    try:
        if cls == "Person":
            n = d.get("primary_name") or {}
            surs = n.get("surname_list") or []
            sur = (surs[0].get("surname") if surs else "") or ""
            return f"{n.get('first_name') or ''} {sur}".strip()
        if cls == "Event":
            t = d.get("type")
            if isinstance(t, dict):
                kind = t.get("string") or EVENT_TYPES.get(t.get("value"), "")
            else:
                kind = t if isinstance(t, str) else ""
            return " · ".join(x for x in (kind, d.get("description") or "") if x)[:70]
        if cls == "Family":
            return ""
        if cls == "Place":
            return ((d.get("name") or {}).get("value")) or ""
        if cls == "Citation":
            return (d.get("page") or "")[:70]
        if cls == "Source":
            return (d.get("title") or "")[:70]
        if cls == "Note":
            txt = ((d.get("text") or {}).get("string")) or ""
            return txt.strip().replace("\n", " ")[:70]
        if cls == "Media":
            return (d.get("desc") or "")[:70]
    except Exception:  # noqa: BLE001 — labels are cosmetic, never fail the page
        pass
    return ""


def _week_detail(txns: list[dict], week: str) -> dict:
    """Per-day counts and per-object rows for one week."""
    day_sets = [{"added": set(), "edited": set(), "deleted": set()} for _ in DAYS]
    objects: dict[tuple, dict] = {}
    in_action: dict[str, set] = {"added": set(), "edited": set(), "deleted": set()}

    for txn in txns:
        if txn.get("undo"):
            continue
        ts = _txn_ts(txn)
        if not ts or _week_of(ts) != week:
            continue
        wd = datetime.fromtimestamp(ts).date().weekday()
        for ch in txn.get("changes") or []:
            if ch.get("ref_handle"):
                continue
            action = ACTIONS.get(ch.get("trans_type"))
            cls = ch.get("obj_class")
            if not action or not isinstance(cls, str):
                continue
            key = (cls, ch.get("obj_handle"))
            payload = ch.get("new_data") or ch.get("old_data") or {}
            rec = objects.setdefault(key, {
                "cls": cls, "handle": ch.get("obj_handle"),
                "gramps_id": "", "label": "", "day": wd})
            rec["day"] = wd
            if isinstance(payload, dict):
                rec["gramps_id"] = payload.get("gramps_id") or rec["gramps_id"]
                rec["label"] = _label(cls, payload) or rec["label"]
            day_sets[wd][action].add(key)
            in_action[action].add(key)

    days = [{"day": DAYS[i],
             "added": len(d["added"]),
             "edited": len(d["edited"] - d["added"]),
             "deleted": len(d["deleted"])}
            for i, d in enumerate(day_sets)]

    def rows(keys: set) -> list[dict]:
        rs = sorted((objects[k] for k in keys),
                    key=lambda r: (r["cls"], r["gramps_id"] or "~"))
        return [{"cls": r["cls"] if r["cls"] in CLASSES else "Other",
                 "gramps_id": r["gramps_id"], "handle": r["handle"],
                 "label": r["label"], "day": DAYS[r["day"]]} for r in rs]

    return {"week": week, "days": days,
            "added": rows(in_action["added"]),
            "edited": rows(in_action["edited"] - in_action["added"]),
            "deleted": rows(in_action["deleted"])}
