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
    try:
        text = TYPES_PATH.read_text()
    except FileNotFoundError:
        raise RuntimeError(
            f"citation types file missing: {TYPES_PATH}. The "
            "bifrost/modules/data/ directory must be present in the checkout"
        ) from None
    raw = yaml.safe_load(text)
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


COMPOSE_SCHEMA = {
    "type": "object",
    "properties": {
        "analysis": {
            "type": "string",
            "description": (
                "Working notes: record type and era, governing style section "
                "and its template, jurisdiction path, locator format, "
                "abstract-vs-FRN split."
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
            "description": "Repository call number for the source (NAD ref, NARA pub, RG...).",
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
                "page": {"type": "string", "description": "Locator: page/entry/dwelling/image..."},
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
                        "Research abstract of what THIS record entry states. the "
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
and the HOUSE STYLE GUIDES below exactly. The guides override generic EE \
practice wherever they differ.

- Two citation layers only: First Reference Note (full, specific-to-general) \
and Short Reference Note. Never produce a Source List Entry.
- Also produce an ABSTRACT note: plain-prose summary of what the record \
actually states (ages/birth years, birthplaces, occupations, marital status, \
relationships, and any other content). Extracted facts go in the abstract, \
NEVER in the reference notes. The notes only locate the record and name the \
subject and co-residents by relationship.
- Punctuation: commas within a layer, semicolons between major layers, \
colons for sub-elements, parentheses for publication details.
- Records accessed through a digital platform get a dual-layer citation: \
the database/image layer AND the underlying original, joined with "citing". \
The Gramps Source represents the original record series; platform homepage \
goes in pubinfo, the deep URL goes in the First Reference Note.
- Foreign-language record-series names and creating bodies get a bracketed \
English gloss in the First Reference Note on first use (EE 2.28), e.g. \
Husförhörslängder [household examinations], Atti di Matrimonio [marriage \
acts]. Gloss in the FRN only, never in the source title field; \
the Short Reference Note drops it.
- The citation date field is always left blank, never return a date.
- Dates in prose as day month year (15 March 1870). Full state names in the \
First Reference Note, traditional abbreviations (Minn., Wis.) in the Short  \
never USPS two-letter codes.
- Mark anything missing as [NEEDED: description] rather than inventing it.
- Gramps confidence from the GPS assessment per the guides' §10 tables: \
original+primary+direct=4; original+primary+indirect or clean image of an \
original=3; derivative+primary or original+secondary=2; \
derivative+secondary or compiled-without-images=1; hearsay/undetermined=0.
- Use the house-style guide section that matches the record's country and \
type; follow that section's jurisdiction paths, locator tokens, title forms \
and worked examples exactly. Only for record kinds with NO dedicated section \
fall back to the principles of the most closely related section (same region \
or language family, never mix conventions from unrelated sections.

Before emitting, re-read your draft against the mistakes that recur:
- Jurisdiction: the place hierarchy must follow the record's OWN administrative \
path, not a different system borrowed by analogy (an urban civil census uses \
the civil administrative hierarchy, never the ecclesiastical one), with no \
place name repeated across levels. Use the guide's place-name forms (modern \
unless it says otherwise) and NEVER invent a name pairing or parenthetical the \
guide does not sanction; match the guide's worked-example depth (don't add \
intermediate levels it omits). Order the source title largest-jurisdiction-first; \
the reference note runs specific-to-general.
- Locator: matches the guide's token format exactly (including forms like \
"district [N] [name]") and omits anything the source title already implies.
- First Reference Note: birth years, birthplaces, occupations and other facts \
extracted FROM the record are kept OUT of it, the FRN locates the record and \
names the subject and co-residents by relationship only; extracted detail \
belongs in the abstract.

When an existing Source was chosen, return null for repository and source \
and compose only the citation locator, confidence, notes and quality \
consistent with that source's established style."""

HOUSE_STYLE_SKELETON = """\
# House style master

Your citation house style. The AI citation composer reads everything above
the final scan-metadata part on every compose call so edits here take
effect immediately. Replace the notes in each part with your own
conventions; delete what you don't need.

# Part 0: Gramps field map

How citation elements map onto Gramps fields for your tree: source title,
author, pubinfo, abbrev; the citation page string; which notes a citation
carries.

# Part A: Common conventions

Rules that apply to every record type: punctuation, date forms, name
forms, the citation layers (First Reference Note, Short Reference Note,
abstract), and how confidence is assigned.

# Part B: Record-type guides

One section per country or record type you work with (B.1, B.2, ...), each
with jurisdiction paths, locator formats, title forms, and worked examples
copied from real citations you consider exemplary.

## B.1 [Country / record type]

# Part C: Scan metadata

Everything from this heading on is NOT sent to the citation composer. Use
it for document-processing conventions or anything else.
"""

_configured_master: Path | None = None


def configure_house_style(path: Path | str | None) -> None:
    global _configured_master
    _configured_master = Path(path) if path else None


def master_path() -> Path:
    """Resolved fresh every call so a master created after startup is picked up live"""
    if _configured_master is not None:
        return _configured_master
    docker_repo = Path("/app/repo")
    if docker_repo.is_dir():
        return docker_repo / "house_style_master.md"
    return Path(__file__).resolve().parents[2] / "house_style_master.md"


def _master_citation_style() -> str:
    """Everything before '# Part C' in the master doc, read fresh; '' when unreachable"""
    try:
        text = master_path().read_text(encoding="utf-8")
    except OSError:
        return ""
    lines = text.splitlines()
    cut = next((i for i, ln in enumerate(lines) if ln.startswith("# Part C")),
               len(lines))
    return "\n".join(lines[:cut]).strip()


def has_house_style() -> bool:
    return bool(_master_citation_style())


def system_prompt() -> str:
    return (SYSTEM_PROMPT_CORE + "\n\n===== HOUSE STYLE GUIDES =====\n\n"
            + _master_citation_style())


def compose_prompt(
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
record's country and exact type, not a neighbouring guide applied by analogy?
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
extracted FROM the record must NOT appear here. the FRN locates the record and \
names the subject and co-residents by relationship only.
- Abstract: those extracted facts (ages/birth years, birthplaces, occupations, \
relationships) belong in the abstract note. it must capture them and must not \
be empty when the record states such detail.
- Mechanics: dual-layer "citing" for platform records, the citation date left \
blank, confidence per the GPS tables, and [NEEDED: …] for anything genuinely \
absent rather than an invented value.

In the analysis field, list each issue found and the fix you applied (or "no \
changes needed"). Then return the FULL corrected draft, keeping every \
already-correct field verbatim."""


async def _critique(anthropic: AnthropicClient, record_context: str,
                    draft: dict) -> dict:
    """ second pass. matched_* keys are stripped and re-attached by the caller"""
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
    user = compose_prompt(rt, fields, media, existing_source, today, event_context)
    draft = await anthropic.complete_structured(
        system_prompt(), user, COMPOSE_SCHEMA, max_tokens=8000)
    if critique:
        draft = await _critique(anthropic, user, draft)
    if existing_source:
        draft["repository"] = None
        draft["source"] = None
    return draft


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

DUMP_LEAD = """The user has described a record in labeled sections below \
(citation subject, transcript, URLs, additional details). Extract every \
citation element from them."""

EVENT_ONLY_LEAD = """No freeform description was provided, compose a citation \
for the EVENT described above. Infer the standard source record that would \
evidence an event of that type, place, and era (e.g. the civil or church \
register, census, or vital record appropriate to the jurisdiction), and mark \
every locator and identifier you cannot derive (page, entry, volume, \
film/roll, access URL) as [NEEDED: …]. Never invent specifics."""

DUMP_MATCHING = """MATCHING: a catalog of the tree's existing sources and \
repositories follows. If the record clearly belongs to one of the existing \
sources (same record series e.g. another page of the same census county, \
another entry in the same parish register volume), set matched_source_gramps_id \
and return null for repository/source. If only the repository matches (new \
source held by a known archive/platform), set matched_repository_gramps_id and \
draft the new source. Match conservatively: a different county, volume, or year \
range is a DIFFERENT source. When matched, compose the citation in that \
source's established style."""

# Back-compat alias
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


async def media_citations(gramps: GrampsClient, media_handle: str) -> list[dict]:
    """Citations already on a media object, with context to compose a sibling in the same style"""
    out = []
    for c in await gramps._paged("/citations/"):
        if not any(mr.get("ref") == media_handle for mr in c.get("media_list", [])):
            continue
        src = None
        if c.get("source_handle"):
            try:
                src = await gramps.get_object("sources", c["source_handle"])
            except Exception:  # noqa: BLE001
                src = None
        notes = []
        for nh in c.get("note_list") or []:
            try:
                n = await gramps.get_object("notes", nh)
            except Exception:  # noqa: BLE001
                continue
            txt = ((n.get("text") or {}).get("string") or "").strip()
            if txt:
                notes.append({"type": str(n.get("type") or ""), "text": txt})
        out.append({
            "gramps_id": c.get("gramps_id", ""),
            "page": c.get("page", ""),
            "confidence": c.get("confidence"),
            "source_gramps_id": (src or {}).get("gramps_id"),
            "source_handle": (src or {}).get("handle"),
            "source_title": (src or {}).get("title", ""),
            "notes": notes,
        })
    return out


def dump_context(
    subject: str = "",
    transcript: str = "",
    urls: str = "",
    dump: str = "",
    media: dict | None = None,
    event_context: str | None = None,
    existing_citations: list[dict] | None = None,
    today: str = "",
) -> str:
    """Record-description block shared by the compose call and the critique pass"""
    parts = [f"Today's date (for access dates): {today}"]
    if event_context:
        parts.append(
            "EVENT this citation documents (the citation will be attached to it):\n"
            + event_context)
    if media:
        parts.append(f"MEDIA OBJECT this citation will be attached to:\n"
                     f"  title: {media.get('desc')}\n  gramps id: {media.get('gramps_id')}")
    if subject.strip():
        parts.append(
            "CITATION SUBJECT the specific fact or claim this citation "
            "supports (name this subject in the reference notes, and assess "
            "evidence type and confidence for THIS claim: the same record gives "
            "Direct evidence of one fact and Indirect of another e.g. a birth "
            "year computed from a stated age is Indirect):\n  " + subject.strip())
    if existing_citations:
        lines = []
        for i, c in enumerate(existing_citations, 1):
            head = f"  [{i}] citation {c.get('gramps_id') or '?'}"
            if c.get("source_gramps_id"):
                head += f" in source {c['source_gramps_id']} ({c.get('source_title') or ''})"
            head += f" | locator: {c.get('page') or '(none)'} | confidence: {c.get('confidence')}"
            lines.append(head)
            for n in c.get("notes", []):
                lines.append(f"      {n['type'] or 'note'}: {' '.join(n['text'].split())}")
        parts.append(
            "CITATIONS ALREADY ATTACHED TO THIS MEDIA OBJECT the new citation "
            "cites another aspect of the SAME record. Do NOT rebuild from "
            "scratch: set matched_source_gramps_id to the existing source and "
            "return null for repository/source; keep the locator and the "
            "reference notes' wording consistent with the existing citation, "
            "changing only what the new subject requires (the subject named, "
            "the GPS quality and confidence assessed for this claim, and an "
            "abstract focused on this aspect rather than repeating the whole "
            "record):\n" + "\n".join(lines))
    if transcript.strip():
        parts.append(
            "TRANSCRIPT of the record (from Paperless may include an English "
            "translation section):\n" + transcript.strip())
    if urls.strip():
        parts.append(
            "URLS for the record, one per line, each optionally followed by its "
            "role (permanent, archived, database entry). Place them per the "
            "house rules deep/permanent URL in the First Reference Note, "
            "platform homepage in pubinfo:\n" + urls.strip())
    if dump.strip():
        parts.append(f"ADDITIONAL DETAILS:\n{dump.strip()}")
    return "\n\n".join(parts)


async def compose_from_dump(
    anthropic: AnthropicClient,
    dump: str,
    media: dict | None,
    sources: list[dict],
    repos: list[dict],
    event_context: str | None = None,
    critique: bool = True,
    subject: str = "",
    transcript: str = "",
    urls: str = "",
    existing_citations: list[dict] | None = None,
) -> dict:
    today = datetime.now().strftime("%-d %B %Y")
    has_content = any(s.strip() for s in (subject, transcript, urls, dump))
    lead = DUMP_LEAD if has_content else EVENT_ONLY_LEAD
    record_ctx = dump_context(
        subject=subject, transcript=transcript, urls=urls, dump=dump,
        media=media, event_context=event_context,
        existing_citations=existing_citations, today=today)
    parts = [lead + "\n\n" + DUMP_MATCHING, record_ctx,
             _catalog(sources, repos), _type_guidance_digest(),
             "Compose the EE citation now."]
    draft = await anthropic.complete_structured(
        system_prompt(), "\n\n".join(parts), DUMP_SCHEMA, max_tokens=8000)

    if critique:
        ctx = record_ctx if has_content else record_ctx + "\n\n" + EVENT_ONLY_LEAD
        matched_now = next(
            (s for s in sources
             if s["gramps_id"] == draft.get("matched_source_gramps_id")), None)
        if matched_now:
            ctx += ("\n\nMATCHED EXISTING SOURCE (the draft composes a citation "
                    "within it; keep its established style):\n"
                    f"  title: {matched_now.get('title')}\n"
                    f"  author: {matched_now.get('author')}\n"
                    f"  pubinfo: {matched_now.get('pubinfo')}\n"
                    f"  abbrev: {matched_now.get('abbrev')}")
        revised = await _critique(anthropic, ctx, draft)
        revised["matched_source_gramps_id"] = draft.get("matched_source_gramps_id")
        revised["matched_repository_gramps_id"] = draft.get("matched_repository_gramps_id")
        for k in ("source", "repository", "call_number"):
            if draft.get(k) is not None and revised.get(k) is None:
                revised[k] = draft[k]
        draft = revised

    def _from_existing(gid: str | None) -> dict | None:
        for c in existing_citations or []:
            if gid and c.get("source_gramps_id") == gid and c.get("source_handle"):
                return {"handle": c["source_handle"], "gramps_id": gid,
                        "title": c.get("source_title", "")}
        return None

    mid = draft.get("matched_source_gramps_id")
    matched_source = (next((s for s in sources if s["gramps_id"] == mid), None)
                      or _from_existing(mid))
    matched_repo = next(
        (r for r in repos if r["gramps_id"] == draft.get("matched_repository_gramps_id")), None)
    if existing_citations and not matched_source and not draft.get("source"):
        sids = {c.get("source_gramps_id") for c in existing_citations
                if c.get("source_gramps_id")}
        if len(sids) == 1:
            sid = next(iter(sids))
            matched_source = (next((s for s in sources if s["gramps_id"] == sid), None)
                              or _from_existing(sid))
            if matched_source:
                draft["matched_source_gramps_id"] = matched_source["gramps_id"]
    if matched_source:
        draft["source"] = None
        draft["repository"] = None
    elif matched_repo:
        draft["repository"] = None
    return {"draft": draft, "matched_source": matched_source,
            "matched_repository": matched_repo}


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
    """Create whatever is new (repository → source → note → citation) and return the ids"""
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


async def context(gramps: GrampsClient) -> dict:
    """Everything the citations page needs to start: types, sources, repos"""
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
    cited: set[str] = set()
    for c in await gramps._paged("/citations/"):
        for mr in c.get("media_list", []):
            if mr.get("ref"):
                cited.add(mr["ref"])
    return cited


async def media_listing(gramps: GrampsClient, uncited_only: bool) -> list[dict]:
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


def _event_date_text(ev: dict) -> str:
    d = ev.get("date") or {}
    return d.get("text") or (str(d.get("year")) if d.get("year") else "")


async def uncited_events(gramps: GrampsClient) -> list[dict]:
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
    """One event in full plus the media worth citing it from (its own and its participants')"""
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
