from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import yaml

from ..core.clients import GrampsClient
from ..core.clients.anthropic import AnthropicClient
from ..core.ids import generate_handle

log = logging.getLogger("bifrost.citations")

TYPES_PATH = Path(__file__).parent / "data" / "citation_types.yaml"


def load_citation_types() -> dict:
    raw = yaml.safe_load(TYPES_PATH.read_text())
    digital = raw.get("digital_access_fields") or []
    types = []
    for t in raw["types"]:
        merged = dict(t)
        merged["fields"] = list(t["fields"]) + digital
        types.append(merged)
    return {"groups": raw["groups"], "types": types}


def next_sequential_id(prefix: str, existing: set[str]) -> str:
    pat = re.compile(rf"^{prefix}(\d+)$")
    nums = [int(m.group(1)) for i in existing if (m := pat.match(i))]
    n = (max(nums) + 1) if nums else 1
    return f"{prefix}{n:04d}"


# Composition

COMPOSE_SCHEMA = {
    "type": "object",
    "properties": {
        "analysis": {
            "type": "string",
            "description": (
                "FILL THIS FIRST — reason on paper before drafting any other "
                "field. Work through, in order: (1) the record's country, era and "
                "exact type, and WHICH house-style guide section governs it (a "
                "Norwegian 1875 census → the Norwegian guide, NOT the Swedish "
                "one); quote the specific worked-example template you will "
                "follow. (2) The correct JURISDICTION hierarchy for THIS record "
                "type — use the source's own administrative path and never borrow "
                "a different system by analogy (an urban census follows amt → "
                "kjøpstad → census district, NOT the ecclesiastical prestegjeld), "
                "and never repeat the same place name across levels. (3) The exact "
                "locator/district token format the guide specifies (e.g. its "
                "'district [N] [name]' form), copying its punctuation and order, "
                "omitting anything the source title already implies. (4) The "
                "FRN-vs-abstract split: the First Reference Note LOCATES the "
                "record and names the subject and co-residents by relationship "
                "only — extracted facts (birth years, birthplaces, occupations) "
                "go in the abstract, NEVER the FRN. Then draft the fields to "
                "match this analysis."
            ),
        },
        "repository": {
            "type": ["object", "null"],
            "description": "Null when an existing repository was chosen.",
            "properties": {
                "name": {"type": "string"},
                "type": {"type": "string", "enum": [
                    "Archive", "Library", "Church", "Collection", "Association",
                    "Web site", "Bookstore", "Cemetery", "Safe"]},
                "url": {"type": ["string", "null"]},
            },
            "required": ["name", "type"],
        },
        "call_number": {
            "type": ["string", "null"],
            "description": "Repository call number for the source (NAD ref, NARA pub, RG…).",
        },
        "source": {
            "type": ["object", "null"],
            "description": "Null when an existing source was chosen.",
            "properties": {
                "title": {"type": "string"},
                "author": {"type": "string"},
                "pubinfo": {"type": "string"},
                "abbrev": {"type": "string"},
            },
            "required": ["title", "author", "pubinfo", "abbrev"],
        },
        "citation": {
            "type": "object",
            "properties": {
                "page": {"type": "string", "description": "Locator: page/entry/dwelling/image…"},
                "confidence": {"type": "integer", "minimum": 0, "maximum": 4,
                               "description": "Gramps: 0 very low … 4 very high, per the GPS mapping."},
            },
            "required": ["page", "confidence"],
        },
        "notes": {
            "type": "object",
            "properties": {
                "first_reference": {"type": "string"},
                "short_reference": {"type": "string"},
                "abstract": {
                    "type": ["string", "null"],
                    "description": (
                        "Research abstract of what THIS record entry states — the "
                        "facts extracted from the record that do NOT belong in the "
                        "reference notes: the subject's and co-residents' stated "
                        "details (ages/birth years, birthplaces, occupations, "
                        "marital status, relationships) and any other content the "
                        "record gives. Plain prose. Null ONLY when the record "
                        "carries no extractable detail (e.g. an event-only draft "
                        "of [NEEDED] placeholders)."
                    ),
                },
            },
            "required": ["first_reference", "short_reference"],
        },
        "quality": {
            "type": "object",
            "properties": {
                "source_type": {"type": "string", "enum": ["Original", "Derivative", "Authored"]},
                "information_type": {"type": "string", "enum": ["Primary", "Secondary", "Undetermined"]},
                "evidence_type": {"type": "string", "enum": ["Direct", "Indirect", "Negative"]},
                "note": {"type": "string", "description": "One sentence."},
            },
            "required": ["source_type", "information_type", "evidence_type", "note"],
        },
    },
    "required": ["analysis", "citation", "notes", "quality"],
}

SYSTEM_PROMPT_CORE = """You construct Evidence Explained (EE) citations for \
genealogical records and map them to Gramps Web fields. Follow EE conventions \
and the HOUSE STYLE GUIDES below exactly — the guides override generic EE \
practice wherever they differ.

- Two citation layers only: First Reference Note (full, specific-to-general) \
and Short Reference Note. Never produce a Source List Entry.
- Also produce an ABSTRACT note: plain-prose summary of what the record \
actually states (ages/birth years, birthplaces, occupations, marital status, \
relationships, and any other content). Extracted facts go in the abstract, \
NEVER in the reference notes — the notes only locate the record and name the \
subject and co-residents by relationship.
- Punctuation: commas within a layer, semicolons between major layers, \
colons for sub-elements, parentheses for publication details.
- Records accessed through a digital platform get a dual-layer citation: \
the database/image layer AND the underlying original, joined with "citing". \
The Gramps Source represents the original record series; platform homepage \
goes in pubinfo, the deep URL goes in the First Reference Note.
- Foreign-language record-series names and creating bodies get a bracketed \
English gloss in the First Reference Note on first use (EE 2.28): \
Husförhörslängder [household examinations], Politiets registerblade [police \
register pages], Fangeprotokoll [prisoner rolls], Älvdals häradsrätt [Älvdal \
district court]. Gloss in the FRN only — never in the source title field; \
the Short Reference Note drops it.
- The citation date field is always left blank — never return a date.
- Dates in prose as day month year (15 March 1870). Full state names in the \
First Reference Note, traditional abbreviations (Minn., Wis.) in the Short — \
never USPS two-letter codes.
- Mark anything missing as [NEEDED: description] rather than inventing it.
- Gramps confidence from the GPS assessment per the guides' §10 tables: \
original+primary+direct=4; original+primary+indirect or clean image of an \
original=3; derivative+primary or original+secondary=2; \
derivative+secondary or compiled-without-images=1; hearsay/undetermined=0.
- Use the dedicated house-style guide that matches the record's country and \
type — Norwegian, Swedish, US, and published/personal records EACH have their \
own guide section; follow that section's jurisdiction paths, locator tokens, \
title forms and worked examples exactly. Only for kinds with NO dedicated \
section (e.g. Danish, Italian, German) fall back to the nearest guide's \
principles (the Swedish guide for other Nordic records, the US guide for other \
English-language records).

Before emitting, re-read your draft against the mistakes that recur:
- Jurisdiction: the place hierarchy must follow the record's OWN administrative \
path, not a different system borrowed by analogy (an urban census uses amt → \
kjøpstad → census district, never the ecclesiastical prestegjeld), with no \
place name repeated across levels. Use the guide's place-name forms (modern \
unless it says otherwise) and NEVER invent a name pairing or parenthetical the \
guide does not sanction; match the guide's worked-example depth (don't add \
härad/län levels it omits). Order the source title largest-jurisdiction-first; \
the reference note runs specific-to-general.
- Locator: matches the guide's token format exactly (including forms like \
"district [N] [name]") and omits anything the source title already implies.
- First Reference Note: birth years, birthplaces, occupations and other facts \
extracted FROM the record are kept OUT of it — the FRN locates the record and \
names the subject and co-residents by relationship only; extracted detail \
belongs in the abstract.

When an existing Source was chosen, return null for repository and source \
and compose only the citation locator, confidence, notes and quality \
consistent with that source's established style."""

_STYLE_DIR = Path(__file__).parent / "data"
# The single source of truth, edited live by Peter and bind-mounted into the
# container at /app/house_style_master.md (same resolution as config.yaml).
_MASTER = Path(__file__).resolve().parents[2] / "house_style_master.md"


def _master_citation_style() -> str:
    """The citation-relevant body of the master house-style doc: everything
    BEFORE '# Part C' — i.e. Part 0 (incl. the Gramps field map), Part A (common
    conventions) and Part B.1–B.4 (per-region/record-type guides). Part C is
    Paperless scan metadata and the appendices are change logs, both irrelevant
    (and Part C's Title rules conflict with citation subjects), so they're cut.
    Read fresh each call so live edits to the master take effect immediately.
    Returns '' if the master isn't reachable."""
    try:
        text = _MASTER.read_text(encoding="utf-8")
    except OSError:
        return ""
    lines = text.splitlines()
    cut = next((i for i, ln in enumerate(lines) if ln.startswith("# Part C")),
               len(lines))
    return "\n".join(lines[:cut]).strip()


def _style_guides() -> str:
    master = _master_citation_style()
    if master:
        return master
    # Fallback only if the master is missing (e.g. bind mount absent): the older,
    # incomplete per-region guides bundled in data/.
    return "\n\n---\n\n".join(
        p.read_text() for p in sorted(_STYLE_DIR.glob("style_*.md")))


def system_prompt() -> str:
    return SYSTEM_PROMPT_CORE + "\n\n===== HOUSE STYLE GUIDES =====\n\n" + _style_guides()


def build_compose_prompt(
    record_type: dict | None,
    fields: dict,
    media: dict | None,
    existing_source: dict | None,
    today: str,
    event_context: str | None = None,
) -> str:
    parts = [f"Today's date (for access dates): {today}\n"]
    if event_context:
        parts.append(
            "EVENT this citation documents (the citation will be attached to it; "
            "compose a citation for the record that evidences this event):\n"
            + event_context)
    if existing_source:
        parts.append(
            "EXISTING SOURCE (compose a citation within it; keep its style):\n"
            f"  title: {existing_source.get('title')}\n"
            f"  author: {existing_source.get('author')}\n"
            f"  pubinfo: {existing_source.get('pubinfo')}\n"
            f"  abbrev: {existing_source.get('abbrev')}\n")
    if record_type:
        parts.append(f"RECORD TYPE: {record_type['label']}")
        if record_type.get("guidance"):
            parts.append(f"TYPE GUIDANCE: {record_type['guidance']}")
    if media:
        parts.append(
            "MEDIA OBJECT this citation will be attached to:\n"
            f"  title: {media.get('desc')}\n"
            f"  gramps id: {media.get('gramps_id')}\n")
    field_lines = [f"  {k}: {v}" for k, v in fields.items() if str(v).strip()]
    parts.append("PROVIDED DETAILS:\n" + ("\n".join(field_lines) or "  (none)"))
    parts.append("Compose the EE citation now.")
    return "\n\n".join(parts)


CRITIQUE_LEAD = """A DRAFT citation (JSON below) was produced for the record \
described below. Review it ADVERSARIALLY against the HOUSE STYLE GUIDES above \
and return a CORRECTED draft. Assume there is at least one thing to fix; only \
conclude "no changes needed" after actually checking each point.

Check, in order:
- Guide selection: is the draft built from the guide section matching the \
record's country and exact type — not a neighbouring guide applied by analogy?
- Jurisdiction: does the place hierarchy follow the record's OWN administrative \
path (an urban census is amt → kjøpstad → census district, NEVER the \
ecclesiastical prestegjeld), with no place name repeated across levels? Are the \
guide's place-name forms used (modern unless it says otherwise) with NO invented \
name pairing or parenthetical (e.g. no "Värmlands (Carlstads) län"), and the \
guide's worked-example depth matched (no extra härad/län levels it omits)? Is \
the title largest-jurisdiction-first and the reference note specific-to-general?
- Locator / title: the guide's exact token format (e.g. "district [N] [name]"), \
nothing the source title already implies, native series names with the bracketed \
English gloss in the First Reference Note only.
- First Reference Note: birth years, birthplaces, occupations and other facts \
extracted FROM the record must NOT appear here — the FRN locates the record and \
names the subject and co-residents by relationship only.
- Abstract: those extracted facts (ages/birth years, birthplaces, occupations, \
relationships) belong in the abstract note — it must capture them and must not \
be empty when the record states such detail.
- Mechanics: dual-layer "citing" for platform records, the citation date left \
blank, confidence per the GPS tables, and [NEEDED: …] for anything genuinely \
absent rather than an invented value.

In the analysis field, list each issue found and the fix you applied (or "no \
changes needed"). Then return the FULL corrected draft, keeping every \
already-correct field verbatim."""


async def _critique(anthropic: AnthropicClient, record_context: str,
                    draft: dict) -> dict:
    """Second adversarial pass: re-read the draft against the guides and return a
    corrected one. Reviews the citation text/notes only — dump-mode matching ids
    are stripped first and re-attached by the caller."""
    review = {k: v for k, v in draft.items() if not k.startswith("matched_")}
    user = (CRITIQUE_LEAD
            + "\n\n===== THE RECORD =====\n" + record_context
            + "\n\n===== DRAFT TO REVIEW (JSON) =====\n"
            + json.dumps(review, ensure_ascii=False, indent=2))
    return await anthropic.complete_structured(
        system_prompt(), user, COMPOSE_SCHEMA, max_tokens=8000)


async def compose(
    anthropic: AnthropicClient,
    record_type_key: str | None,
    fields: dict,
    media: dict | None,
    existing_source: dict | None,
    event_context: str | None = None,
    critique: bool = True,
) -> dict:
    types = load_citation_types()["types"]
    rt = next((t for t in types if t["key"] == record_type_key), None)
    today = datetime.now().strftime("%-d %B %Y")
    user = build_compose_prompt(rt, fields, media, existing_source, today, event_context)
    draft = await anthropic.complete_structured(
        system_prompt(), user, COMPOSE_SCHEMA, max_tokens=8000)
    if critique:
        draft = await _critique(anthropic, user, draft)
    if existing_source:
        draft["repository"] = None
        draft["source"] = None
    return draft


# ---------------------------------------------------------------------------
# Dump mode — freeform text in, matched-or-new source + citation out
# ---------------------------------------------------------------------------

DUMP_SCHEMA = {
    **COMPOSE_SCHEMA,
    "properties": {
        **COMPOSE_SCHEMA["properties"],
        "matched_source_gramps_id": {
            "type": ["string", "null"],
            "description": "gramps_id of the EXISTING source this record belongs to, "
                           "or null if none truly fits. Never force a match.",
        },
        "matched_repository_gramps_id": {
            "type": ["string", "null"],
            "description": "When drafting a NEW source: gramps_id of an existing "
                           "repository that holds it, or null to create one.",
        },
    },
}

DUMP_LEAD = """The user has pasted a freeform description of a record \
("the dump"). Extract every citation element from it."""

EVENT_ONLY_LEAD = """No freeform description was provided — compose a citation \
for the EVENT described above. Infer the standard source record that would \
evidence an event of that type, place, and era (e.g. the civil or church \
register, census, or vital record appropriate to the jurisdiction), and mark \
every locator and identifier you cannot derive (page, entry, volume, \
film/roll, access URL) as [NEEDED: …]. Never invent specifics."""

DUMP_MATCHING = """MATCHING: a catalog of the tree's existing sources and \
repositories follows. If the record clearly belongs to one of the existing \
sources (same record series — e.g. another page of the same census county, \
another entry in the same parish register volume), set matched_source_gramps_id \
and return null for repository/source. If only the repository matches (new \
source held by a known archive/platform), set matched_repository_gramps_id and \
draft the new source. Match conservatively: a different county, volume, or year \
range is a DIFFERENT source. When matched, compose the citation in that \
source's established style."""

# Back-compat alias (the full dump-mode instruction block).
DUMP_INSTRUCTIONS = DUMP_LEAD + "\n\n" + DUMP_MATCHING


def _catalog(sources: list[dict], repos: list[dict]) -> str:
    src_lines = [
        f"  {s['gramps_id']} | {s['title']} | {s.get('abbrev') or ''} | {(s.get('pubinfo') or '')[:90]}"
        for s in sources
    ]
    repo_lines = [f"  {r['gramps_id']} | {r['name']} | {r['type']}" for r in repos]
    return ("EXISTING SOURCES:\n" + "\n".join(src_lines)
            + "\n\nEXISTING REPOSITORIES:\n" + "\n".join(repo_lines))


def _type_guidance_digest() -> str:
    lines = []
    for t in load_citation_types()["types"]:
        if t.get("guidance"):
            lines.append(f"- {t['label']}: {' '.join(t['guidance'].split())}")
    return "DOMAIN NOTES BY RECORD KIND:\n" + "\n".join(lines)


async def compose_from_dump(
    anthropic: AnthropicClient,
    dump: str,
    media: dict | None,
    sources: list[dict],
    repos: list[dict],
    event_context: str | None = None,
    critique: bool = True,
) -> dict:
    today = datetime.now().strftime("%-d %B %Y")
    has_dump = bool(dump.strip())
    lead = DUMP_LEAD if has_dump else EVENT_ONLY_LEAD
    parts = [lead + "\n\n" + DUMP_MATCHING, f"Today's date (for access dates): {today}"]
    if event_context:
        parts.append(
            "EVENT this citation documents (the citation will be attached to it):\n"
            + event_context)
    if media:
        parts.append(f"MEDIA OBJECT this citation will be attached to:\n"
                     f"  title: {media.get('desc')}\n  gramps id: {media.get('gramps_id')}")
    parts.append(_catalog(sources, repos))
    parts.append(_type_guidance_digest())
    if has_dump:
        parts.append(f"THE DUMP:\n{dump.strip()}")
    parts.append("Compose the EE citation now.")
    draft = await anthropic.complete_structured(
        system_prompt(), "\n\n".join(parts), DUMP_SCHEMA, max_tokens=8000)

    if critique:
        ctx = []
        if event_context:
            ctx.append("EVENT this citation documents:\n" + event_context)
        if media:
            ctx.append(f"MEDIA: {media.get('desc')} ({media.get('gramps_id')})")
        ctx.append(f"Today's date (for access dates): {today}")
        ctx.append(f"THE DUMP:\n{dump.strip()}" if has_dump else EVENT_ONLY_LEAD)
        revised = await _critique(anthropic, "\n\n".join(ctx), draft)
        # The critique reviews citation text, not matching — keep the first
        # pass's match decision so server-side resolution below is unaffected.
        revised["matched_source_gramps_id"] = draft.get("matched_source_gramps_id")
        revised["matched_repository_gramps_id"] = draft.get("matched_repository_gramps_id")
        draft = revised

    # Resolve matches server-side; a hallucinated id degrades to "new".
    matched_source = next(
        (s for s in sources if s["gramps_id"] == draft.get("matched_source_gramps_id")), None)
    matched_repo = next(
        (r for r in repos if r["gramps_id"] == draft.get("matched_repository_gramps_id")), None)
    if matched_source:
        draft["source"] = None
        draft["repository"] = None
    elif matched_repo:
        draft["repository"] = None
    return {"draft": draft, "matched_source": matched_source,
            "matched_repository": matched_repo}


# ---------------------------------------------------------------------------
# Save — create the chain bottom-up, link the media
# ---------------------------------------------------------------------------

def _note_text(notes: dict) -> str:
    return (f"FIRST REFERENCE NOTE:\n{notes['first_reference'].strip()}\n\n"
            f"SHORT REFERENCE NOTE:\n{notes['short_reference'].strip()}")


async def save(
    gramps: GrampsClient,
    conn: sqlite3.Connection,
    draft: dict,
    media_handle: str | None,
    repository_handle: str | None,
    source_handle: str | None,
    event_handle: str | None = None,
) -> dict:
    """Create whatever is new (repository → source → note → citation), link
    the media, optionally attach the citation to an event, and return the
    created/used ids. Partial-failure honest: each created object is reported
    even if a later step fails."""
    created: dict = {}
    now = int(datetime.utcnow().timestamp())

    async def mint(api_path: str, prefix: str) -> str:
        items = await gramps._paged(f"/{api_path}/", keys="gramps_id")
        return next_sequential_id(
            prefix, {i["gramps_id"] for i in items if i.get("gramps_id")})

    if repository_handle is None and draft.get("repository"):
        r = draft["repository"]
        repository_handle = generate_handle()
        repo_gid = await mint("repositories", "R")
        repo_obj = {
            "_class": "Repository", "handle": repository_handle, "gramps_id": repo_gid,
            "name": r["name"], "type": r["type"], "change": now,
            "address_list": [], "note_list": [], "tag_list": [], "private": False,
            "urls": ([{"_class": "Url", "path": r["url"], "desc": "", "type": "Home URL",
                       "private": False}] if r.get("url") else []),
        }
        await gramps.create_object(repo_obj)
        created["repository"] = repo_gid

    if source_handle is None and draft.get("source"):
        s = draft["source"]
        source_handle = generate_handle()
        src_gid = await mint("sources", "S")
        reporefs = []
        if repository_handle:
            reporefs.append({
                "_class": "RepoRef", "ref": repository_handle,
                "call_number": draft.get("call_number") or "",
                "media_type": "Unknown", "note_list": [], "private": False,
            })
        src_obj = {
            "_class": "Source", "handle": source_handle, "gramps_id": src_gid,
            "title": s["title"], "author": s["author"], "pubinfo": s["pubinfo"],
            "abbrev": s["abbrev"], "change": now, "reporef_list": reporefs,
            "media_list": [], "note_list": [], "attribute_list": [],
            "tag_list": [], "private": False,
        }
        await gramps.create_object(src_obj)
        created["source"] = src_gid

    if source_handle is None:
        raise ValueError("no source chosen and none drafted")

    # Citation reference note (FRN/SRN) + optional research abstract note. Mint
    # both N ids from one query so a lagging Gramps index can't duplicate them.
    existing_notes = {i["gramps_id"] for i
                      in await gramps._paged("/notes/", keys="gramps_id")
                      if i.get("gramps_id")}
    note_handle = generate_handle()
    note_gid = next_sequential_id("N", existing_notes)
    existing_notes.add(note_gid)
    await gramps.create_object({
        "_class": "Note", "handle": note_handle, "gramps_id": note_gid,
        "text": {"_class": "StyledText", "string": _note_text(draft["notes"]), "tags": []},
        "type": "Citation", "format": 0, "change": now,
        "tag_list": [], "private": False,
    })
    created["note"] = note_gid

    note_list = [note_handle]
    abstract = (draft["notes"].get("abstract") or "").strip()
    if abstract:
        abstract_handle = generate_handle()
        abstract_gid = next_sequential_id("N", existing_notes)
        await gramps.create_object({
            "_class": "Note", "handle": abstract_handle, "gramps_id": abstract_gid,
            "text": {"_class": "StyledText", "string": abstract, "tags": []},
            "type": "Abstract", "format": 0, "change": now,
            "tag_list": [], "private": False,
        })
        created["abstract_note"] = abstract_gid
        note_list.append(abstract_handle)

    c = draft["citation"]
    citation_handle = generate_handle()
    cit_gid = await mint("citations", "C")
    cit_obj = {
        "_class": "Citation", "handle": citation_handle, "gramps_id": cit_gid,
        "source_handle": source_handle, "page": c["page"],
        "confidence": int(c["confidence"]), "change": now,
        "note_list": note_list, "media_list": [], "attribute_list": [],
        "tag_list": [], "private": False,
    }
    if media_handle:
        cit_obj["media_list"] = [{
            "_class": "MediaRef", "ref": media_handle, "rect": [],
            "attribute_list": [], "citation_list": [], "note_list": [], "private": False,
        }]
    await gramps.create_object(cit_obj)
    created["citation"] = cit_gid

    # Attach the citation to an event (event.citation_list) — the event-cite flow.
    if event_handle:
        ev = await gramps.get_object("events", event_handle)
        cl = ev.get("citation_list") or []
        if citation_handle not in cl:
            cl.append(citation_handle)
            ev["citation_list"] = cl
            await gramps.update_object("events", event_handle, ev)
        created["event"] = ev.get("gramps_id") or event_handle

    with conn:
        conn.execute(
            "INSERT INTO runs (job, status, started_at, finished_at, summary)"
            " VALUES ('citations.save', 'ok', ?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"),
             datetime.now().isoformat(timespec="seconds"),
             str(created)),
        )
    return created


# ---------------------------------------------------------------------------
# Lookups for the page
# ---------------------------------------------------------------------------

async def context(gramps: GrampsClient) -> dict:
    """Everything the citations page needs to start: types, sources, repos."""
    sources = await gramps._paged("/sources/")
    repos = await gramps._paged("/repositories/")
    return {
        **load_citation_types(),
        "sources": [{"handle": s["handle"], "gramps_id": s["gramps_id"],
                     "title": s.get("title", ""), "author": s.get("author", ""),
                     "pubinfo": s.get("pubinfo", ""), "abbrev": s.get("abbrev", "")}
                    for s in sources],
        "repositories": [{"handle": r["handle"], "gramps_id": r["gramps_id"],
                          "name": r.get("name", ""), "type": str(r.get("type", ""))}
                         for r in repos],
    }


async def cited_media_set(gramps: GrampsClient) -> set[str]:
    """Handles of every media object that already has at least one citation."""
    cited: set[str] = set()
    for c in await gramps._paged("/citations/"):
        for mr in c.get("media_list", []):
            if mr.get("ref"):
                cited.add(mr["ref"])
    return cited


async def media_listing(gramps: GrampsClient, uncited_only: bool) -> list[dict]:
    """All media, lightest useful shape, flagged with citation status."""
    cited = await cited_media_set(gramps)
    out = []
    for m in await gramps.list_media():
        is_cited = m["handle"] in cited
        if uncited_only and is_cited:
            continue
        src = next((a["value"] for a in m.get("attribute_list", [])
                    if a.get("type") in ("Paperless ID", "Immich ID")), None)
        out.append({
            "handle": m["handle"], "gramps_id": m.get("gramps_id", ""),
            "title": m.get("desc") or m.get("gramps_id", ""),
            "cited": is_cited,
            "origin": ("paperless" if any(a.get("type") == "Paperless ID"
                                          for a in m.get("attribute_list", []))
                       else "immich" if src else "other"),
        })
    out.sort(key=lambda r: (r["cited"], r["title"].lower()))
    return out


# ---------------------------------------------------------------------------
# Event-cite flow — cycle uncited events, cite each from related media
# ---------------------------------------------------------------------------

def _event_date_text(ev: dict) -> str:
    d = ev.get("date") or {}
    return d.get("text") or (str(d.get("year")) if d.get("year") else "")


async def uncited_events(gramps: GrampsClient) -> list[dict]:
    """Light list of events with no citation attached — the cycler's queue."""
    events = await gramps._paged(
        "/events/", keys="handle,gramps_id,type,date,place,description,citation_list")
    places = {
        p["handle"]: ((p.get("name") or {}).get("value") or p.get("gramps_id", ""))
        for p in await gramps._paged("/places/", keys="handle,gramps_id,name")}
    out = [{
        "handle": e["handle"], "gramps_id": e.get("gramps_id", ""),
        "type": str(e.get("type") or "Event"),
        "date": _event_date_text(e),
        "place": places.get(e.get("place"), ""),
        "description": e.get("description", ""),
    } for e in events if not e.get("citation_list")]
    out.sort(key=lambda r: (r["type"], r["date"]))
    return out


async def event_detail(
    gramps: GrampsClient, handle: str, cited: set[str]
) -> dict:
    """Full detail for one event plus the media worth citing it from: media
    attached to the event itself and to its participant people."""
    e = await gramps.get_object("events", handle, profile="all", backlinks="true")
    prof = e.get("profile") or {}
    parts = (prof.get("participants") or {}).get("people") or []
    participants, person_handles = [], []
    for p in parts:
        per = p.get("person") or {}
        b = (per.get("birth") or {}).get("date") or ""
        d = (per.get("death") or {}).get("date") or ""
        lifeparts = ([f"b. {b}"] if b else []) + ([f"d. {d}"] if d else [])
        life = f" ({', '.join(lifeparts)})" if lifeparts else ""
        participants.append({
            "name": per.get("name_display") or per.get("gramps_id") or "?",
            "gramps_id": per.get("gramps_id", ""),
            "role": p.get("role") or "",
            "life": life,
        })
        if per.get("handle"):
            person_handles.append(per["handle"])

    # related media: the event's own, then each participant's
    refs: list[str] = [mr["ref"] for mr in (e.get("media_list") or []) if mr.get("ref")]
    for ph in person_handles:
        try:
            per = await gramps.get_object("people", ph)
        except Exception:  # noqa BLE001
            continue
        refs += [mr["ref"] for mr in (per.get("media_list") or []) if mr.get("ref")]

    media, seen = [], set()
    for ref in refs:
        if ref in seen:
            continue
        seen.add(ref)
        try:
            m = await gramps.get_object("media", ref)
        except Exception:  # noqa BLE001
            continue
        media.append({
            "handle": ref, "gramps_id": m.get("gramps_id", ""),
            "title": m.get("desc") or m.get("gramps_id", ""),
            "cited": ref in cited,
        })

    # event facts passed to the composer as grounding (not the source desc)
    ctx = [f"Event: {prof.get('type') or e.get('type') or 'Event'}"
           + (f", {prof['date']}" if prof.get("date") else "")]
    if prof.get("place"):
        ctx.append(f"Place: {prof['place']}")
    if participants:
        ctx.append("People: " + "; ".join(p["name"] + p["life"] for p in participants))
    if e.get("description"):
        ctx.append(f"Description: {e['description']}")

    return {
        "handle": handle,
        "gramps_id": e.get("gramps_id", ""),
        "summary": prof.get("summary", ""),
        "type": str(prof.get("type") or e.get("type") or ""),
        "date": prof.get("date", "") or _event_date_text(e),
        "place": prof.get("place", ""),
        "participants": participants,
        "media": media,
        "context": "\n".join(ctx),
    }
