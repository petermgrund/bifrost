"""Citation generator — EE citations composed by Claude, saved to Gramps.

Flow: pick a media object (any synced doc/photo, new or old) → pick an
existing Source or describe a new one via record-type field checklists →
Claude composes the EE layers + Gramps field mapping (editable draft) →
save creates Repository/Source/Citation/Note as needed and links the media.

The EE rules and output conventions are ported from Peter's ee-us-citations
skill and matched to the tree's real data: one Citation-type note with
FIRST/SHORT REFERENCE NOTE blocks; confidence as Gramps 0-4; dual-layer
"citing" for platform-accessed records; [NEEDED: …] placeholders.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import yaml

from ..core.clients import GrampsClient
from ..core.clients.anthropic import AnthropicClient
from .sync_immich import generate_handle

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
    """Next id in the tree's native sequential convention (C0001, S0042…).

    Bare random 6-char ids are reserved for MEDIA objects only (deletion-
    collision safety + physical photo labels); everything else follows the
    Gramps-style sequence. Ids not matching ^PREFIX\\d+$ (e.g. legacy
    N_XXXXXX transcription notes) are ignored when finding the max.
    """
    pat = re.compile(rf"^{prefix}(\d+)$")
    nums = [int(m.group(1)) for i in existing if (m := pat.match(i))]
    n = (max(nums) + 1) if nums else 1
    return f"{prefix}{n:04d}"


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------

COMPOSE_SCHEMA = {
    "type": "object",
    "properties": {
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
    "required": ["citation", "notes", "quality"],
}

SYSTEM_PROMPT_CORE = """You construct Evidence Explained (EE) citations for \
genealogical records and map them to Gramps Web fields. Follow EE conventions \
and the HOUSE STYLE GUIDES below exactly — the guides override generic EE \
practice wherever they differ.

- Two citation layers only: First Reference Note (full, specific-to-general) \
and Short Reference Note. Never produce a Source List Entry.
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
- For record kinds without a dedicated guide (Norwegian, Danish, Italian…), \
apply the nearest guide's principles — the Swedish guide for Nordic records \
(collection-led titles, native series names, glosses, NAD-style call \
numbers), the US guide for English-language records.

When an existing Source was chosen, return null for repository and source \
and compose only the citation locator, confidence, notes and quality \
consistent with that source's established style."""

_STYLE_DIR = Path(__file__).parent / "data"


def _style_guides() -> str:
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
) -> str:
    parts = [f"Today's date (for access dates): {today}\n"]
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


async def compose(
    anthropic: AnthropicClient,
    record_type_key: str | None,
    fields: dict,
    media: dict | None,
    existing_source: dict | None,
) -> dict:
    types = load_citation_types()["types"]
    rt = next((t for t in types if t["key"] == record_type_key), None)
    today = datetime.now().strftime("%-d %B %Y")
    user = build_compose_prompt(rt, fields, media, existing_source, today)
    draft = await anthropic.complete_structured(system_prompt(), user, COMPOSE_SCHEMA)
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

DUMP_INSTRUCTIONS = """The user has pasted a freeform description of a record \
("the dump"). Extract every citation element from it.

MATCHING: a catalog of the tree's existing sources and repositories follows. \
If the record clearly belongs to one of the existing sources (same record \
series — e.g. another page of the same census county, another entry in the \
same parish register volume), set matched_source_gramps_id and return null \
for repository/source. If only the repository matches (new source held by a \
known archive/platform), set matched_repository_gramps_id and draft the new \
source. Match conservatively: a different county, volume, or year range is a \
DIFFERENT source. When matched, compose the citation in that source's \
established style."""


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
) -> dict:
    today = datetime.now().strftime("%-d %B %Y")
    parts = [DUMP_INSTRUCTIONS, f"Today's date (for access dates): {today}"]
    if media:
        parts.append(f"MEDIA OBJECT this citation will be attached to:\n"
                     f"  title: {media.get('desc')}\n  gramps id: {media.get('gramps_id')}")
    parts.append(_catalog(sources, repos))
    parts.append(_type_guidance_digest())
    parts.append(f"THE DUMP:\n{dump.strip()}")
    parts.append("Compose the EE citation now.")
    draft = await anthropic.complete_structured(
        system_prompt(), "\n\n".join(parts), DUMP_SCHEMA)

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
) -> dict:
    """Create whatever is new (repository → source → note → citation), link
    the media, and return the created/used ids. Partial-failure honest: each
    created object is reported even if a later step fails."""
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

    note_handle = generate_handle()
    note_gid = await mint("notes", "N")
    await gramps.create_object({
        "_class": "Note", "handle": note_handle, "gramps_id": note_gid,
        "text": {"_class": "StyledText", "string": _note_text(draft["notes"]), "tags": []},
        "type": "Citation", "format": 0, "change": now,
        "tag_list": [], "private": False,
    })
    created["note"] = note_gid

    c = draft["citation"]
    citation_handle = generate_handle()
    cit_gid = await mint("citations", "C")
    cit_obj = {
        "_class": "Citation", "handle": citation_handle, "gramps_id": cit_gid,
        "source_handle": source_handle, "page": c["page"],
        "confidence": int(c["confidence"]), "change": now,
        "note_list": [note_handle], "media_list": [], "attribute_list": [],
        "tag_list": [], "private": False,
    }
    if media_handle:
        cit_obj["media_list"] = [{
            "_class": "MediaRef", "ref": media_handle, "rect": [],
            "attribute_list": [], "citation_list": [], "note_list": [], "private": False,
        }]
    await gramps.create_object(cit_obj)
    created["citation"] = cit_gid

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


async def media_listing(gramps: GrampsClient, uncited_only: bool) -> list[dict]:
    """All media, lightest useful shape, flagged with citation status."""
    cited: set[str] = set()
    for c in await gramps._paged("/citations/"):
        for mr in c.get("media_list", []):
            if mr.get("ref"):
                cited.add(mr["ref"])
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
