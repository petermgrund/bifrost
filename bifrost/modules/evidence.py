"""Claims, proofs and audits over the citations in Gramps.

A read-only view after Evidentia's discipline. A claim is one thing a citation is attached to
(an event, a family, a child reference, a person, a name) and the `Cited for` word that names
it; a proof is everything attached to one claim, with each citation's confidence, source type
and `Evidence` line, the Report note that argues the conclusion and the To Do note that says
what to look for next. Nothing here writes to Gramps or to bifrost.db.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from ..core.clients import GrampsClient
from ..core.config import EvidenceConfig

CONFIDENCE = {0: "Very Low", 1: "Low", 2: "Normal", 3: "High", 4: "Very High"}
HIGH = 3
# a derivative source cannot carry more than High, an authored work more than Normal
SOURCE_CEILING = {"original": 4, "derivative": 3, "derived": 3, "authored": 2}
EVIDENCE_CLASSES = ("direct", "indirect", "negative")
OWN_ATTRIBUTES = ("Cited for", "Evidence", "Record URL")
RELATION_WORDS = {
    "family": ("spouse", "marriage"),
    "childref": ("mother", "father", "parents", "child"),
    "person": ("identity",),
    "name": ("name",),
    "media": ("depicts",),
    "place": ("place",),
}
STAR_TYPES = {"birth": ("Birth",), "marriage": ("Marriage",), "death": ("Death",),
              "burial": ("Burial", "Cremation")}

_EVIDENCE_RE = re.compile(r"^\s*(?P<word>[^:;]+?)\s*:\s*(?P<cls>direct|indirect|negative)\s*(?:;\s*(?P<why>.*))?$",
                          re.IGNORECASE | re.DOTALL)
_PAREN_RE = re.compile(r"\(([^()]*)\)")
# parentheticals the page string may keep: locators and disambiguators
_LOCATOR_RE = re.compile(
    r"^(?:(?:image|images|page|pages|pdf|slide|fold3|serial|certified copy|unikt id|urban residence|"
    r"roll|frame|line|lines|folio)\b|(?:p|pp|no|col|fol|entry no)\.)", re.IGNORECASE)
_YEARS_RE = re.compile(r"^\d{4}(\s*[-–]\s*\d{4})?$")
_DISAMBIG_RE = re.compile(r"^(?:[\w.'-]+\s)?(?:b|d|bapt|m|bur|senior|junior|sr|jr|the elder|the younger|elder|younger)\b\.?",
                          re.IGNORECASE)


@dataclass
class Tree:
    """Everything the section reads, by handle"""
    citations: dict[str, dict] = field(default_factory=dict)
    events: dict[str, dict] = field(default_factory=dict)
    people: dict[str, dict] = field(default_factory=dict)
    families: dict[str, dict] = field(default_factory=dict)
    sources: dict[str, dict] = field(default_factory=dict)
    notes: dict[str, dict] = field(default_factory=dict)
    tags: dict[str, str] = field(default_factory=dict)
    loaded_at: float = 0.0
    # event handle -> [(person handle, role)] for the events a person takes part in
    event_people: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    event_families: dict[str, list[str]] = field(default_factory=dict)
    by_gramps_id: dict[str, dict[str, str]] = field(default_factory=dict)

    def index(self) -> None:
        self.event_people = {}
        self.event_families = {}
        for h, p in self.people.items():
            for ref in p.get("event_ref_list") or []:
                self.event_people.setdefault(ref.get("ref"), []).append((h, ref.get("role") or ""))
        for h, f in self.families.items():
            for ref in f.get("event_ref_list") or []:
                self.event_families.setdefault(ref.get("ref"), []).append(h)
        self.by_gramps_id = {
            kind: {o.get("gramps_id"): h for h, o in objs.items() if o.get("gramps_id")}
            for kind, objs in (("citation", self.citations), ("event", self.events), ("person", self.people),
                               ("family", self.families), ("source", self.sources))}


PEOPLE_KEYS = ("handle,gramps_id,primary_name,alternate_names,event_ref_list,family_list,parent_family_list,"
               "citation_list,attribute_list,note_list,tag_list,change,gender,profile")
EVENT_KEYS = "handle,gramps_id,type,date,place,description,tag_list,note_list,citation_list,attribute_list,change,profile"
FAMILY_KEYS = ("handle,gramps_id,father_handle,mother_handle,child_ref_list,event_ref_list,citation_list,"
               "attribute_list,tag_list,note_list,change")
SOURCE_KEYS = "handle,gramps_id,title,author,abbrev,pubinfo,attribute_list,media_list,note_list,change"
NOTE_KEYS = "handle,gramps_id,type,text,change"


async def load_tree(gramps: GrampsClient) -> Tree:
    """Read the whole tree once; a few hundred objects of each kind take about a second"""
    t = Tree()
    t.citations = {c["handle"]: c for c in await gramps.list_objects("citations", backlinks="true")}
    t.events = {e["handle"]: e for e in await gramps.list_objects("events", keys=EVENT_KEYS, profile="self", locale="en")}
    t.people = {p["handle"]: p for p in await gramps.list_objects("people", keys=PEOPLE_KEYS, profile="self", locale="en")}
    t.families = {f["handle"]: f for f in await gramps.list_objects("families", keys=FAMILY_KEYS)}
    t.sources = {s["handle"]: s for s in await gramps.list_objects("sources", keys=SOURCE_KEYS)}
    t.notes = {n["handle"]: n for n in await gramps.list_objects("notes", keys=NOTE_KEYS)}
    t.tags = {tg["handle"]: tg.get("name") or "" for tg in await gramps.list_objects("tags", keys="handle,name")}
    t.loaded_at = time.time()
    t.index()
    return t


# --- reading one citation ---

def split_values(value: str | None) -> list[str]:
    """The words in one attribute value: comma or semicolon separated, lower case, trimmed"""
    return [w for w in (" ".join(part.split()).lower() for part in re.split(r"[,;]", value or "")) if w]


def attrs(obj: dict, name: str) -> list[str]:
    return [a.get("value") or "" for a in obj.get("attribute_list") or [] if a.get("type") == name]


def cited_for(citation: dict) -> list[dict]:
    """One entry per `Cited for` row: its words and whether it holds more than one"""
    return [{"raw": raw, "words": split_values(raw)} for raw in attrs(citation, "Cited for")]


def cited_words(citation: dict) -> list[str]:
    return [w for row in cited_for(citation) for w in row["words"]]


def evidence_rows(citation: dict) -> list[dict]:
    """`Evidence` rows parsed as `<word>: <direct|indirect|negative>[; <why>]`; ok is False when
    a row is not in that shape"""
    out = []
    for raw in attrs(citation, "Evidence"):
        m = _EVIDENCE_RE.match(raw)
        if m:
            out.append({"raw": raw, "ok": True, "word": " ".join(m["word"].split()).lower(),
                        "cls": m["cls"].lower(), "why": (m["why"] or "").strip()})
        else:
            out.append({"raw": raw, "ok": False, "word": None, "cls": None, "why": raw.strip()})
    return out


def parentheticals(page: str | None) -> list[str]:
    return [m.group(1).strip() for m in _PAREN_RE.finditer(page or "")]


def parenthetical_allowed(text: str) -> bool:
    """A locator (image 66, pp. 563-656, serial 1083), a year or span, a code with no prose, or a
    disambiguator (b. 1773, d. 1948, senior) may stay in the page string; anything else explains
    the claim and belongs in an `Evidence` row"""
    t = text.strip()
    if not t:
        return True
    if _LOCATOR_RE.match(t) or _YEARS_RE.match(t):
        return True
    if not re.search(r"[a-zåäöæø]", t):
        return True
    clauses = [c.strip() for c in t.split(",") if c.strip()]
    return all(_DISAMBIG_RE.match(c) or _YEARS_RE.match(c) or _LOCATOR_RE.match(c) for c in clauses)


def stray_parentheticals(page: str | None) -> list[str]:
    return [p for p in parentheticals(page) if not parenthetical_allowed(p)]


def source_type(tree: Tree, citation: dict) -> str | None:
    src = tree.sources.get(citation.get("source_handle") or "")
    if not src:
        return None
    values = attrs(src, "Source type")
    return " ".join(values[0].split()).lower() if values and values[0].strip() else None


def confidence_ceiling(stype: str | None) -> int | None:
    return SOURCE_CEILING.get(stype or "")


def note_text(note: dict | None) -> str:
    if not note:
        return ""
    text = note.get("text")
    return (text.get("string") if isinstance(text, dict) else text) or ""


def notes_of(tree: Tree, handles: list[str] | None) -> list[dict]:
    out = []
    for h in handles or []:
        n = tree.notes.get(h)
        if n:
            out.append({"handle": h, "gramps_id": n.get("gramps_id"), "type": n.get("type") or "",
                        "text": note_text(n), "change": n.get("change") or 0})
    return out


def tag_names(tree: Tree, obj: dict) -> list[str]:
    return [tree.tags.get(h, "?") for h in obj.get("tag_list") or []]


# --- names and titles ---

def person_name(tree: Tree, handle: str | None) -> str:
    p = tree.people.get(handle or "")
    if not p:
        return "(unknown)"
    prof = p.get("profile") or {}
    if prof.get("name_display"):
        return prof["name_display"].strip(", ") or "(unknown)"
    name = p.get("primary_name") or {}
    surname = (name.get("surname_list") or [{}])[0].get("surname") or ""
    return f"{surname}, {name.get('first_name') or ''}".strip(", ") or "(unknown)"


def _year(text: str) -> str:
    m = re.search(r"\d{4}", text or "")
    return m.group(0) if m else ""


def person_years(tree: Tree, handle: str) -> str:
    """Birth and death years from the profile's formatted dates, however fuzzy: about 1850 → 1850"""
    prof = (tree.people.get(handle) or {}).get("profile") or {}
    b = _year((prof.get("birth") or {}).get("date") or "")
    d = _year((prof.get("death") or {}).get("date") or "")
    return f"{b or '…'}–{d or '…'}" if (b or d) else ""


def event_participants(tree: Tree, handle: str) -> list[str]:
    """Primary people first, then any family the event belongs to"""
    names = [person_name(tree, ph) for ph, role in tree.event_people.get(handle, []) if role == "Primary"]
    if not names:
        names = [person_name(tree, ph) for ph, _role in tree.event_people.get(handle, [])]
    for fh in tree.event_families.get(handle, []):
        names.append(family_name(tree, fh))
    return names


def family_name(tree: Tree, handle: str) -> str:
    f = tree.families.get(handle) or {}
    return " & ".join(person_name(tree, h) for h in (f.get("father_handle"), f.get("mother_handle")) if h) or "(family)"


def event_title(tree: Tree, handle: str) -> str:
    e = tree.events.get(handle) or {}
    who = event_participants(tree, handle)
    return f"{e.get('type') or 'Event'} of {', '.join(who)}" if who else (e.get("type") or "Event")


def event_when(tree: Tree, handle: str) -> dict:
    e = tree.events.get(handle) or {}
    prof = e.get("profile") or {}
    return {"date": prof.get("date") or ((e.get("date") or {}).get("text") or ""),
            "place": prof.get("place") or "", "description": e.get("description") or ""}


def citation_reference(tree: Tree, c: dict) -> str:
    src = tree.sources.get(c.get("source_handle") or "") or {}
    head = src.get("abbrev") or src.get("title") or "(no source)"
    return f"{head}, {c['page']}" if c.get("page") else head


def gramps_url(public_url: str, kind: str, gramps_id: str | None) -> str | None:
    return f"{public_url}/{kind}/{gramps_id}" if public_url and gramps_id else None


# --- where a citation is attached ---

def _in(citation_handle: str, obj: dict | None) -> bool:
    return bool(obj) and citation_handle in (obj.get("citation_list") or [])


def attachments(tree: Tree, citation: dict) -> list[dict]:
    """Every slot the citation is attached to, found from its backlinks and the slot's own
    citation list: event, family, childref (with the child), person, name, media, place.
    Links from note text are not attachments"""
    ch = citation["handle"]
    out: list[dict] = []
    links = citation.get("backlinks") or {}
    for h in links.get("event") or []:
        e = tree.events.get(h)
        if e is None:
            out.append({"kind": "event", "handle": h, "gramps_id": None, "title": "(event not loaded)"})
            continue
        kind = "event"
        if not _in(ch, e) and any(_in(ch, a) for a in e.get("attribute_list") or []):
            kind = "eventattr"
        out.append({"kind": kind, "handle": h, "gramps_id": e.get("gramps_id"), "title": event_title(tree, h),
                    "type": e.get("type") or ""})
    for h in links.get("family") or []:
        f = tree.families.get(h)
        if f is None:
            out.append({"kind": "family", "handle": h, "gramps_id": None, "title": "(family not loaded)"})
            continue
        found = False
        for ref in f.get("child_ref_list") or []:
            if _in(ch, ref):
                found = True
                out.append({"kind": "childref", "handle": h, "gramps_id": f.get("gramps_id"),
                            "title": f"{person_name(tree, ref.get('ref'))}, child of {family_name(tree, h)}",
                            "child": ref.get("ref")})
        if _in(ch, f) or not found:
            out.append({"kind": "family", "handle": h, "gramps_id": f.get("gramps_id"), "title": family_name(tree, h)})
    for h in links.get("person") or []:
        p = tree.people.get(h)
        if p is None:
            out.append({"kind": "person", "handle": h, "gramps_id": None, "title": "(person not loaded)"})
            continue
        names = [p.get("primary_name") or {}] + list(p.get("alternate_names") or [])
        found = False
        if any(_in(ch, n) for n in names):
            found = True
            out.append({"kind": "name", "handle": h, "gramps_id": p.get("gramps_id"), "title": person_name(tree, h)})
        if _in(ch, p) or not found:
            out.append({"kind": "person", "handle": h, "gramps_id": p.get("gramps_id"), "title": person_name(tree, h)})
    for kind in ("media", "place"):
        for h in links.get(kind) or []:
            out.append({"kind": kind, "handle": h, "gramps_id": None, "title": kind})
    return out


def words_for(cfg: EvidenceConfig, kind: str, event_type: str | None = None) -> set[str]:
    """The `Cited for` words an attachment of this kind accounts for"""
    if kind in ("event", "eventattr"):
        words = {(event_type or "").lower()} if event_type else set()
        for etype, extra in cfg.claim_words:
            if etype == event_type:
                words.update(extra)
        return words
    return set(RELATION_WORDS.get(kind, ()))


def attachment_words(cfg: EvidenceConfig, att: dict) -> set[str]:
    return words_for(cfg, att["kind"], att.get("type"))


# --- the claims of one person ---

def _sortval(e: dict) -> int:
    return (e.get("date") or {}).get("sortval") or 0


def _claim(tree: Tree, kind: str, handle: str, **extra) -> dict:
    return {"kind": kind, "handle": handle, **extra}


def claims_for_person(tree: Tree, person_handle: str) -> list[dict]:
    """Events (own role first), families, parent links, then identity and name. Each claim
    says which citations are attached to it and which `Cited for` words fit it"""
    p = tree.people.get(person_handle)
    if not p:
        return []
    pid = p.get("gramps_id")
    claims: list[dict] = []

    def event_claim(e: dict, role: str, title: str) -> dict:
        return _claim(tree, "event", e["handle"], id=f"event:{e['gramps_id']}", gramps_id=e["gramps_id"],
                      title=title, type=e.get("type") or "", role=role, when=event_when(tree, e["handle"]),
                      citations=list(e.get("citation_list") or []), tags=tag_names(tree, e),
                      notes=notes_of(tree, e.get("note_list")))

    # the person's own events and the events of their families, in date order
    dated: list[dict] = []
    for r in p.get("event_ref_list") or []:
        e = tree.events.get(r.get("ref"))
        if e:
            role = r.get("role") or ""
            dated.append(event_claim(e, role, (e.get("type") or "Event") + ("" if role == "Primary" else f" ({role})")))
    spouses: dict[str, str | None] = {}
    for fh in p.get("family_list") or []:
        f = tree.families.get(fh)
        if not f:
            continue
        spouse = f.get("mother_handle") if f.get("father_handle") == person_handle else f.get("father_handle")
        spouses[fh] = spouse
        for r in f.get("event_ref_list") or []:
            e = tree.events.get(r.get("ref"))
            if e:
                dated.append(event_claim(e, r.get("role") or "",
                                         f"{e.get('type') or 'Event'} with {person_name(tree, spouse)}"))
    dated.sort(key=lambda c: (_sortval(tree.events[c["handle"]]), c["gramps_id"] or ""))
    claims.extend(dated)
    for fh, spouse in spouses.items():
        f = tree.families[fh]
        claims.append(_claim(tree, "family", fh, id=f"family:{f['gramps_id']}", gramps_id=f["gramps_id"],
                             title=f"Family with {person_name(tree, spouse)}", type="Family", role="",
                             when={"date": "", "place": "", "description": ""},
                             citations=list(f.get("citation_list") or []), tags=tag_names(tree, f),
                             notes=notes_of(tree, f.get("note_list"))))
    for fh in p.get("parent_family_list") or []:
        f = tree.families.get(fh)
        if not f:
            continue
        ref = next((r for r in f.get("child_ref_list") or [] if r.get("ref") == person_handle), {})
        claims.append(_claim(tree, "childref", fh, id=f"childref:{f['gramps_id']}:{pid}", gramps_id=f["gramps_id"],
                             title=f"Child of {family_name(tree, fh)}", type="Parents", role="",
                             when={"date": "", "place": "", "description": ""},
                             citations=list(ref.get("citation_list") or []) + list(f.get("citation_list") or []),
                             tags=tag_names(tree, f),
                             notes=notes_of(tree, ref.get("note_list")) + notes_of(tree, f.get("note_list")),
                             child=person_handle))
    names = [p.get("primary_name") or {}] + list(p.get("alternate_names") or [])
    claims.append(_claim(tree, "person", person_handle, id=f"person:{pid}", gramps_id=pid, title="Identity",
                         type="Identity", role="", when={"date": "", "place": "", "description": ""},
                         citations=list(p.get("citation_list") or []), tags=tag_names(tree, p),
                         notes=notes_of(tree, p.get("note_list"))))
    claims.append(_claim(tree, "name", person_handle, id=f"name:{pid}", gramps_id=pid, title="Name",
                         type="Name", role="", when={"date": "", "place": "", "description": ""},
                         citations=[c for n in names for c in n.get("citation_list") or []], tags=[],
                         notes=[]))
    for c in claims:
        c["person"] = pid
    return claims


def claim_by_id(tree: Tree, claim_id: str) -> dict | None:
    """event:E0001, family:F0001, childref:F0001:I0003, person:I0003, name:I0003"""
    parts = claim_id.split(":")
    kind = parts[0]
    ids = tree.by_gramps_id
    if kind == "event" and len(parts) == 2:
        h = ids.get("event", {}).get(parts[1])
        if not h:
            return None
        people = [ph for ph, role in tree.event_people.get(h, []) if role == "Primary"] or \
                 [ph for ph, _r in tree.event_people.get(h, [])] or \
                 [ph for fh in tree.event_families.get(h, [])
                  for ph in ((tree.families.get(fh) or {}).get("father_handle"), (tree.families.get(fh) or {}).get("mother_handle")) if ph]
        for ph in people:
            for c in claims_for_person(tree, ph):
                if c["id"] == claim_id:
                    return c
        e = tree.events[h]
        return _claim(tree, "event", h, id=claim_id, gramps_id=e["gramps_id"], title=event_title(tree, h),
                      type=e.get("type") or "", role="", when=event_when(tree, h), person=None,
                      citations=list(e.get("citation_list") or []), tags=tag_names(tree, e),
                      notes=notes_of(tree, e.get("note_list")))
    if kind == "family" and len(parts) == 2:
        h = ids.get("family", {}).get(parts[1])
        f = tree.families.get(h or "")
        if not f:
            return None
        return _claim(tree, "family", h, id=claim_id, gramps_id=f["gramps_id"], title=family_name(tree, h),
                      type="Family", role="", when={"date": "", "place": "", "description": ""}, person=None,
                      citations=list(f.get("citation_list") or []), tags=tag_names(tree, f),
                      notes=notes_of(tree, f.get("note_list")))
    if kind in ("childref", "person", "name"):
        pid = parts[2] if kind == "childref" and len(parts) == 3 else parts[1] if len(parts) == 2 else None
        ph = ids.get("person", {}).get(pid or "")
        if not ph:
            return None
        return next((c for c in claims_for_person(tree, ph) if c["id"] == claim_id), None)
    return None


# --- the proof of one claim ---

def citation_view(tree: Tree, cfg: EvidenceConfig, c: dict, public_url: str = "") -> dict:
    src = tree.sources.get(c.get("source_handle") or "") or {}
    stype = source_type(tree, c)
    notes = notes_of(tree, c.get("note_list"))
    abstract = "\n\n".join(n["text"] for n in notes if n["type"] == "Abstract")
    return {
        "handle": c["handle"], "gramps_id": c.get("gramps_id"), "page": c.get("page") or "",
        "reference": citation_reference(tree, c),
        "confidence": c.get("confidence"), "confidence_label": CONFIDENCE.get(c.get("confidence"), "?"),
        "source": {"gramps_id": src.get("gramps_id"), "title": src.get("title") or "", "abbrev": src.get("abbrev") or "",
                   "type": stype, "url": gramps_url(public_url, "source", src.get("gramps_id"))},
        "cited_for": cited_for(c), "evidence": evidence_rows(c),
        "abstract": abstract, "notes": [{"type": n["type"], "gramps_id": n["gramps_id"]} for n in notes],
        "media": len(c.get("media_list") or []), "attachments": attachments(tree, c),
        "change": c.get("change") or 0, "url": gramps_url(public_url, "citation", c.get("gramps_id")),
    }


def row_for_claim(tree: Tree, cfg: EvidenceConfig, c: dict, claim: dict, public_url: str = "") -> dict:
    """One citation as it bears on one claim: which words fit, whether an `Evidence` line is
    needed and present, and what is missing"""
    view = citation_view(tree, cfg, c, public_url)
    fits = words_for(cfg, claim["kind"], claim.get("type"))
    words = cited_words(c)
    matched = [w for w in words if w in fits]
    ev = [e for e in view["evidence"] if e["ok"] and e["word"] in fits]
    bad = [e for e in view["evidence"] if not e["ok"]]
    stype = view["source"]["type"]
    needs = (c.get("confidence") or 0) < HIGH or bool(stype and stype != "original")
    missing: list[str] = []
    if not words:
        missing.append("no Cited for row")
    elif not matched:
        missing.append("no Cited for word fits this claim")
    if needs and not ev:
        missing.append("Evidence line needed" + (" (confidence below High)" if (c.get("confidence") or 0) < HIGH
                                                 else f" (source is {stype})"))
    if bad:
        missing.append("Evidence row not in shape")
    view.update({"matched": matched, "evidence_for_claim": ev, "needs_evidence": needs,
                 "missing": missing, "complete": not missing})
    return view


def proof(tree: Tree, cfg: EvidenceConfig, claim: dict, public_url: str = "") -> dict:
    rows = [row_for_claim(tree, cfg, tree.citations[h], claim, public_url)
            for h in claim.get("citations") or [] if h in tree.citations]
    rows.sort(key=lambda r: (-(r["confidence"] or 0), r["gramps_id"] or ""))
    notes = claim.get("notes") or []
    report = next((n for n in notes if n["type"] == "Report"), None)
    todo = next((n for n in notes if n["type"] == "To Do"), None)
    others = [n for n in notes if n not in (report, todo)]
    newest = max((r["change"] for r in rows), default=0)
    stale = [r["gramps_id"] for r in rows if report and r["change"] > report["change"]]
    missing: list[str] = []
    if not rows:
        missing.append("no citation attached")
    for r in rows:
        for m in r["missing"]:
            missing.append(f"{r['gramps_id']}: {m}")
    if rows and not report:
        missing.append("no Report note")
    if stale:
        missing.append("Report note older than " + ", ".join(stale))
    status = [t for t in claim.get("tags") or [] if t in dict(cfg.tags).values()]
    kind_url = {"event": "event", "family": "family", "childref": "family", "person": "person", "name": "person"}
    stated = [{"citation": r["gramps_id"], "cls": e["cls"], "why": e["why"]}
              for r in rows for e in r["evidence_for_claim"] if e["why"]]
    return {
        **{k: claim[k] for k in ("id", "kind", "title", "type", "role", "when", "gramps_id", "person")},
        "url": gramps_url(public_url, kind_url.get(claim["kind"], "event"), claim.get("gramps_id")),
        "tags": claim.get("tags") or [], "status": status,
        "fits": sorted(words_for(cfg, claim["kind"], claim.get("type"))),
        "rows": rows, "stated": stated,
        "report": report, "todo": todo, "other_notes": others,
        "needs_review": stale, "newest_citation": newest,
        "complete": not missing, "missing": missing,
    }


# --- one person ---

def claim_summary(tree: Tree, cfg: EvidenceConfig, claim: dict) -> dict:
    p = proof(tree, cfg, claim)
    return {k: p[k] for k in ("id", "kind", "title", "type", "role", "when", "gramps_id", "status", "complete",
                              "needs_review")} | {
        "citations": len(p["rows"]), "rows_complete": sum(1 for r in p["rows"] if r["complete"]),
        "report": bool(p["report"]), "missing": len(p["missing"])}


def stars(claims: list[dict]) -> dict:
    """Evidentia's five: birth, marriage, death, burial and parents, each 1 when a claim of that
    kind is complete and carries no status tag; parents is 0.5 per proven parent link"""
    def proven(c: dict) -> bool:
        return bool(c["complete"] and not c["status"])
    out = {}
    for star, types in STAR_TYPES.items():
        found = [c for c in claims if c["kind"] == "event" and c["type"] in types and c["role"] in ("Primary", "Family", "")]
        out[star] = 1.0 if any(proven(c) for c in found) else 0.0
    parents = [c for c in claims if c["kind"] == "childref"]
    out["parents"] = 1.0 if any(proven(c) for c in parents) else 0.0
    return out


def person_summary(tree: Tree, cfg: EvidenceConfig, person_handle: str, public_url: str = "") -> dict | None:
    p = tree.people.get(person_handle)
    if not p:
        return None
    claims = [claim_summary(tree, cfg, c) for c in claims_for_person(tree, person_handle)]
    return {
        "handle": person_handle, "gramps_id": p.get("gramps_id"), "name": person_name(tree, person_handle),
        "years": person_years(tree, person_handle), "url": gramps_url(public_url, "person", p.get("gramps_id")),
        "claims": claims, "stars": stars(claims),
        "citations": len({h for c in claims_for_person(tree, person_handle) for h in c["citations"]}),
    }


def people(tree: Tree) -> list[dict]:
    rows = [{"handle": h, "gramps_id": p.get("gramps_id"), "name": person_name(tree, h), "years": person_years(tree, h)}
            for h, p in tree.people.items()]
    rows.sort(key=lambda r: (r["name"].lower(), r["gramps_id"] or ""))
    return rows


# --- audits ---

CHECKS = [
    ("unattached", "Citations attached to nothing",
     "Every citation makes a claim about something. Attach it, or delete it."),
    ("no_cited_for", "Claims with no subject",
     "Attached citations with no `Cited for` row. The row says in words what the attachment says in structure."),
    ("several_in_one", "Several claims in one `Cited for` row",
     "One row per claim, so each can carry its own Evidence line and be matched to its attachment."),
    ("word_unknown", "`Cited for` words outside the vocabulary",
     "The list lives in evidence.cited_for. Add a word when a record type needs one, never a synonym."),
    ("row_unmatched", "`Cited for` rows that no attachment carries",
     "The word names a claim, but the citation is not attached to the object that would hold it."),
    ("attachment_unmatched", "Attachments that no `Cited for` row explains",
     "The citation is attached to an object, but no row says what it is cited for there."),
    ("evidence_missing", "Rows that need an `Evidence` line",
     "Below High confidence, or from a source that is not original, say what the record states and why that is weaker."),
    ("evidence_unparsed", "`Evidence` rows not in shape",
     "`<cited-for word>: direct | indirect | negative; <what the record states and why>`."),
    ("page_parenthetical", "Page strings with a parenthetical that explains",
     "Locators and disambiguators may stay. Anything about the claim or its quality moves to an `Evidence` row."),
    ("record_url_with_media", "`Record URL` on a citation that has media",
     "The media object already carries the record's link."),
    ("attribute_unknown", "Citation attributes outside the model",
     "Only `Cited for`, `Evidence` and `Record URL` belong on a citation."),
    ("confidence_ceiling", "Confidence above the source's ceiling",
     "A derivative source carries at most High, an authored work at most Normal."),
    ("sibling_mismatch", "Sibling citations that drift",
     "Citations on the same entry must share media and notes and differ in confidence; equal confidence means merge."),
    ("unproven_high", "`Unproven` claims with a High citation",
     "Either the citation does not prove it, or the tag is stale."),
    ("needs_review", "Proofs older than their evidence",
     "A citation changed after the Report note was written."),
    ("no_proof", "Claims with two or more citations and no Report note",
     "Several records bear on this; the conclusion deserves an argument."),
]


def _finding(kind: str, gramps_id: str | None, title: str, detail: str, public_url: str = "") -> dict:
    return {"object": kind, "gramps_id": gramps_id, "title": title, "detail": detail,
            "url": gramps_url(public_url, kind, gramps_id)}


def audits(tree: Tree, cfg: EvidenceConfig, public_url: str = "") -> dict:
    found: dict[str, list[dict]] = {cid: [] for cid, _t, _w in CHECKS}
    vocab = set(cfg.cited_for)
    tag_set = set(dict(cfg.tags).values())
    unproven = cfg.tag("unproven")

    def cit(c: dict, detail: str) -> dict:
        return _finding("citation", c.get("gramps_id"), citation_reference(tree, c), detail, public_url)

    by_entry: dict[tuple[str, str], list[dict]] = {}
    for c in sorted(tree.citations.values(), key=lambda x: x.get("gramps_id") or ""):
        atts = attachments(tree, c)
        rows = cited_for(c)
        words = [w for r in rows for w in r["words"]]
        if not atts:
            found["unattached"].append(cit(c, "no attachment"))
        elif not words:
            found["no_cited_for"].append(cit(c, "attached to " + "; ".join(a["title"] for a in atts)))
        for r in rows:
            if len(r["words"]) > 1:
                found["several_in_one"].append(cit(c, f"Cited for: {r['raw']}"))
        for w in words:
            if w not in vocab:
                found["word_unknown"].append(cit(c, f"Cited for: {w}"))
        att_words = [attachment_words(cfg, a) for a in atts]
        for w in words:
            if w in vocab and not any(w in aw for aw in att_words):
                found["row_unmatched"].append(cit(c, f"Cited for: {w}, attached to " + ("; ".join(a["title"] for a in atts) or "nothing")))
        if words:
            for a, aw in zip(atts, att_words):
                if not any(w in aw for w in words):
                    found["attachment_unmatched"].append(cit(c, f"attached to {a['title']} ({a['kind']}); Cited for: {', '.join(words)}"))
        ev = evidence_rows(c)
        for e in ev:
            if not e["ok"]:
                found["evidence_unparsed"].append(cit(c, f"Evidence: {e['raw']}"))
            elif e["word"] not in words:
                found["evidence_unparsed"].append(cit(c, f"Evidence names {e['word']!r}, which no Cited for row holds"))
        stype = source_type(tree, c)
        needs = (c.get("confidence") or 0) < HIGH or bool(stype and stype != "original")
        if needs and words:
            for w in words:
                if w in vocab and not any(e["ok"] and e["word"] == w for e in ev):
                    found["evidence_missing"].append(cit(c, f"{w}: {CONFIDENCE.get(c.get('confidence'), '?')}" + (f", {stype} source" if stype else "")))
        for ptext in stray_parentheticals(c.get("page")):
            found["page_parenthetical"].append(cit(c, f"({ptext})"))
        if attrs(c, "Record URL") and c.get("media_list"):
            found["record_url_with_media"].append(cit(c, "Record URL and media both present"))
        for a in c.get("attribute_list") or []:
            if a.get("type") not in OWN_ATTRIBUTES:
                found["attribute_unknown"].append(cit(c, f"{a.get('type')}: {(a.get('value') or '')[:60]}"))
        ceiling = confidence_ceiling(stype)
        if ceiling is not None and (c.get("confidence") or 0) > ceiling:
            found["confidence_ceiling"].append(cit(c, f"{CONFIDENCE.get(c.get('confidence'), '?')} on a {stype} source"))
        by_entry.setdefault((c.get("source_handle") or "", " ".join((c.get("page") or "").split())), []).append(c)

    for (_s, _p), group in by_entry.items():
        if len(group) < 2:
            continue
        ids = ", ".join(x.get("gramps_id") or "?" for x in group)
        media = {tuple(sorted(m.get("ref") or "" for m in x.get("media_list") or [])) for x in group}
        notes = {tuple(sorted(x.get("note_list") or [])) for x in group}
        confs = [x.get("confidence") for x in group]
        if len(media) > 1:
            found["sibling_mismatch"].append(cit(group[0], f"{ids}: different media"))
        if len(notes) > 1:
            found["sibling_mismatch"].append(cit(group[0], f"{ids}: different notes"))
        if len(set(confs)) < len(confs):
            found["sibling_mismatch"].append(cit(group[0], f"{ids}: same confidence, merge them"))

    seen: set[str] = set()
    for ph in tree.people:
        for claim in claims_for_person(tree, ph):
            if claim["id"] in seen:
                continue
            seen.add(claim["id"])
            if not claim["citations"]:
                continue
            p = proof(tree, cfg, claim)
            kind = {"event": "event", "family": "family", "childref": "family", "person": "person", "name": "person"}[claim["kind"]]
            label = claim["title"] if claim["kind"] != "event" else event_title(tree, claim["handle"])
            if unproven in p["tags"] and any((r["confidence"] or 0) >= HIGH for r in p["rows"]):
                found["unproven_high"].append(_finding(kind, claim["gramps_id"], label,
                                                       ", ".join(r["gramps_id"] for r in p["rows"] if (r["confidence"] or 0) >= HIGH), public_url))
            if p["needs_review"]:
                found["needs_review"].append(_finding(kind, claim["gramps_id"], label, "changed: " + ", ".join(p["needs_review"]), public_url))
            if len(p["rows"]) >= 2 and not p["report"]:
                found["no_proof"].append(_finding(kind, claim["gramps_id"], label, f"{len(p['rows'])} citations", public_url))

    checks = [{"id": cid, "title": title, "why": why, "count": len(found[cid]), "items": found[cid]}
              for cid, title, why in CHECKS]
    return {"checks": checks, "findings": sum(c["count"] for c in checks),
            "citations": len(tree.citations), "tags_present": sorted(tag_set & set(tree.tags.values())),
            "tags_missing": sorted(tag_set - set(tree.tags.values())), "loaded_at": tree.loaded_at}
