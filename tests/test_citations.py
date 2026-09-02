import pytest

from bifrost.modules.citations import (
    COMPOSE_SCHEMA,
    TYPES_PATH,
    _note_text,
    compose_prompt,
    load_citation_types,
)

_NEEDS_TYPES = pytest.mark.skipif(
    not TYPES_PATH.exists(),
    reason="bifrost/modules/data/citation_types.yaml not in this checkout"
           "commit bifrost/modules/data/ (an unanchored 'data/' .gitignore "
           "pattern used to exclude it)")


@_NEEDS_TYPES
def test_types_load_and_merge_digital_fields():
    ctx = load_citation_types()
    types = {t["key"]: t for t in ctx["types"]}
    assert len(types) >= 20
    for t in types.values():
        keys = [f["key"] for f in t["fields"]]
        assert "platform" in keys and "access_date" in keys
        assert len(keys) == len(set(keys)), f"duplicate field keys in {t['key']}"
    for expected in ("swedish-probate", "norwegian-church", "italian-parish",
                     "us-federal-census", "us-newspaper"):
        assert expected in types
    assert {t["group"] for t in ctx["types"]} <= set(ctx["groups"])


def test_note_text_matches_house_convention():
    text = _note_text({
        "first_reference": "Full citation here. ",
        "short_reference": "Short form.",
    })
    assert text == "FIRST REFERENCE NOTE:\nFull citation here.\n\nSHORT REFERENCE NOTE:\nShort form."


def test_prompt_includes_existing_source_style():
    rt = {"key": "x", "label": "Test type", "guidance": "Be precise."}
    p = compose_prompt(
        rt, {"page": "12"}, {"desc": "A doc", "gramps_id": "M1"},
        {"title": "T", "author": "A", "pubinfo": "P", "abbrev": "Ab"},
        "10 June 2026")
    assert "EXISTING SOURCE" in p and "Be precise." in p and "A doc" in p
    assert "page: 12" in p and "10 June 2026" in p


def test_schema_required_paths():
    assert set(COMPOSE_SCHEMA["required"]) == {"analysis", "citation", "notes", "quality"}
    assert COMPOSE_SCHEMA["properties"]["citation"]["properties"]["confidence"]["maximum"] == 4
    assert "date" not in COMPOSE_SCHEMA["properties"]["citation"]["properties"]
    assert "source_list_entry" not in COMPOSE_SCHEMA["properties"]["notes"]["properties"]


def test_system_prompt_carries_style_guides(tmp_path):
    from bifrost.modules import citations as mod
    doc = tmp_path / "house_style_master.md"
    doc.write_text("# Part A\nSENTINEL-STYLE-RULE\n# Part C\nSCAN-META-ONLY\n",
                   encoding="utf-8")
    mod.configure_house_style(doc)
    try:
        assert mod.has_house_style() is True
        p = mod.system_prompt()
    finally:
        mod.configure_house_style(None)
    assert "SENTINEL-STYLE-RULE" in p
    assert "SCAN-META-ONLY" not in p
    assert "Never produce a Source List Entry" in p
    assert "always left blank" in p


def test_house_style_missing_detected(tmp_path):
    from bifrost.modules import citations as mod
    mod.configure_house_style(tmp_path / "does_not_exist.md")
    try:
        assert mod.has_house_style() is False
        assert "HOUSE STYLE GUIDES" in mod.system_prompt()
    finally:
        mod.configure_house_style(None)


def test_dump_context_sections():
    from bifrost.modules.citations import dump_context
    ctx = dump_context(
        subject="Alma Lindqvist's birth year",
        transcript="line one\nline two",
        urls="https://x",
        dump="misc details",
        media={"desc": "Census 1930", "gramps_id": "M9"},
        existing_citations=[{
            "gramps_id": "C0001", "page": "p. 3B", "confidence": 3,
            "source_gramps_id": "S0042", "source_title": "1930 census",
            "notes": [{"type": "Citation", "text": "FRN\ntext"}],
        }],
        today="9 July 2026",
    )
    assert "CITATION SUBJECT" in ctx and "Alma Lindqvist's birth year" in ctx
    assert "Indirect" in ctx
    assert "TRANSCRIPT" in ctx and "line two" in ctx
    assert "URLS" in ctx and "permanent" in ctx
    assert "ADDITIONAL DETAILS:\nmisc details" in ctx
    assert "S0042" in ctx and "matched_source_gramps_id" in ctx
    assert "FRN text" in ctx
    assert "9 July 2026" in ctx and "Census 1930" in ctx


def test_dump_context_omits_empty_sections():
    from bifrost.modules.citations import dump_context
    ctx = dump_context(subject="Nils Holmberg's baptism", today="9 July 2026")
    assert "Nils Holmberg's baptism" in ctx
    assert "TRANSCRIPT" not in ctx
    assert "URLS" not in ctx
    assert "ADDITIONAL DETAILS" not in ctx
    assert "ALREADY ATTACHED" not in ctx
    assert "MEDIA OBJECT" not in ctx


def _draft(**over):
    d = {"analysis": "", "matched_source_gramps_id": None,
         "matched_repository_gramps_id": None,
         "repository": {"name": "Arkiv", "type": "Archive", "url": None},
         "call_number": "NAD/X",
         "source": {"title": "T", "author": "A", "pubinfo": "P", "abbrev": "Ab"},
         "citation": {"page": "p. 1", "confidence": 3},
         "notes": {"first_reference": "f", "short_reference": "s", "abstract": None},
         "quality": {"source_type": "Original", "information_type": "Primary",
                     "evidence_type": "Direct", "note": "n"}}
    d.update(over)
    return d


class _StubAnthropic:
    def __init__(self, *drafts):
        self._drafts = list(drafts)

    async def complete_structured(self, system, user, schema, max_tokens=0):
        return dict(self._drafts.pop(0))


_EXISTING = [{"gramps_id": "C0001", "page": "p. 3B", "confidence": 3,
              "source_gramps_id": "S0042", "source_handle": "H42",
              "source_title": "1930 census", "notes": []}]


@_NEEDS_TYPES
def test_critique_cannot_drop_drafted_source():
    import asyncio
    from bifrost.modules.citations import compose_from_dump
    first = _draft()
    critiqued = _draft(source=None, repository=None, call_number=None)
    r = asyncio.run(compose_from_dump(
        _StubAnthropic(first, critiqued), "", None, sources=[], repos=[],
        subject="X's baptism", existing_citations=_EXISTING))
    assert r["draft"]["source"] == first["source"]
    assert r["draft"]["repository"] == first["repository"]
    assert r["draft"]["call_number"] == "NAD/X"
    assert r["matched_source"] is None


@_NEEDS_TYPES
def test_match_resolves_via_existing_citations_when_catalog_stale():
    import asyncio
    from bifrost.modules.citations import compose_from_dump
    matched = _draft(matched_source_gramps_id="S0042", source=None, repository=None)
    r = asyncio.run(compose_from_dump(
        _StubAnthropic(matched, dict(matched)), "", None, sources=[], repos=[],
        subject="X's baptism", existing_citations=_EXISTING))
    assert r["matched_source"] == {"handle": "H42", "gramps_id": "S0042",
                                   "title": "1930 census"}
    assert r["draft"]["source"] is None


@_NEEDS_TYPES
def test_forced_reuse_when_model_neither_matched_nor_drafted():
    import asyncio
    from bifrost.modules.citations import compose_from_dump
    empty = _draft(source=None, repository=None)
    r = asyncio.run(compose_from_dump(
        _StubAnthropic(empty, dict(empty)), "", None, sources=[], repos=[],
        subject="X's baptism", existing_citations=_EXISTING))
    assert r["matched_source"]["gramps_id"] == "S0042"
    assert r["draft"]["matched_source_gramps_id"] == "S0042"


def test_next_sequential_id():
    from bifrost.modules.citations import next_sequential_id
    assert next_sequential_id("C", {"C0001", "C0036", "C0068"}) == "C0069"
    assert next_sequential_id("N", {"N0134", "N_XNH8SH", "N_RX4ZRR"}) == "N0135"
    assert next_sequential_id("R", set()) == "R0001"
    assert next_sequential_id("C", {"C9999"}) == "C10000"


def test_recent_minted_is_newest_first_and_capped(tmp_path):
    from bifrost.core import db
    from bifrost.modules.citations import recent_minted
    conn = db.connect(tmp_path / "t.db")
    for gid, system, ts in [("A1", "paperless", "2026-09-01T10:00:00"),
                            ("B2", "immich", "2026-09-02T10:00:00+00:00"),
                            ("C3", "paperless", "2026-08-30T10:00:00")]:
        conn.execute(
            "INSERT INTO minted_media (gramps_id, source_system, source_id, title, minted_at) "
            "VALUES (?, ?, '1', 't', ?)", (gid, system, ts))
    conn.commit()
    rows = recent_minted(conn, 1)
    assert [r["gramps_id"] for r in rows] == ["A1"]
    assert [r["gramps_id"] for r in recent_minted(conn)] == ["A1", "C3"]
    assert [r["gramps_id"] for r in recent_minted(conn, source_system="immich")] == ["B2"]
    conn.close()
