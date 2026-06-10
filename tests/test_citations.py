"""Unit tests for the citation module's pure parts."""

from bifrost.modules.citations import (
    COMPOSE_SCHEMA,
    _note_text,
    build_compose_prompt,
    load_citation_types,
)


def test_types_load_and_merge_digital_fields():
    ctx = load_citation_types()
    types = {t["key"]: t for t in ctx["types"]}
    assert len(types) >= 20
    # every type gets the universal digital-access fields merged in
    for t in types.values():
        keys = [f["key"] for f in t["fields"]]
        assert "platform" in keys and "access_date" in keys
        assert len(keys) == len(set(keys)), f"duplicate field keys in {t['key']}"
    # the tree's real record kinds are covered
    for expected in ("swedish-probate", "norwegian-church", "italian-parish",
                     "us-federal-census", "us-newspaper"):
        assert expected in types
    # groups referenced by types all exist
    assert {t["group"] for t in ctx["types"]} <= set(ctx["groups"])


def test_note_text_matches_house_convention():
    text = _note_text({
        "first_reference": "Full citation here. ",
        "short_reference": "Short form.",
    })
    assert text == "FIRST REFERENCE NOTE:\nFull citation here.\n\nSHORT REFERENCE NOTE:\nShort form."


def test_prompt_includes_existing_source_style():
    rt = {"key": "x", "label": "Test type", "guidance": "Be precise."}
    p = build_compose_prompt(
        rt, {"page": "12"}, {"desc": "A doc", "gramps_id": "M1"},
        {"title": "T", "author": "A", "pubinfo": "P", "abbrev": "Ab"},
        "10 June 2026")
    assert "EXISTING SOURCE" in p and "Be precise." in p and "A doc" in p
    assert "page: 12" in p and "10 June 2026" in p


def test_schema_required_paths():
    assert set(COMPOSE_SCHEMA["required"]) == {"citation", "notes", "quality"}
    assert COMPOSE_SCHEMA["properties"]["citation"]["properties"]["confidence"]["maximum"] == 4
    # house style: no citation dates, no source list entries
    assert "date" not in COMPOSE_SCHEMA["properties"]["citation"]["properties"]
    assert "source_list_entry" not in COMPOSE_SCHEMA["properties"]["notes"]["properties"]


def test_system_prompt_carries_style_guides():
    from bifrost.modules.citations import system_prompt
    p = system_prompt()
    assert "Bureau of the Census" in p          # US guide loaded
    assert "Husförhörslängder" in p             # Swedish guide loaded
    assert "Politiets registerblade" in p       # gloss rule with Peter's examples
    assert "Never produce a Source List Entry" in p
    assert "always left blank" in p             # citation date rule


def test_next_sequential_id():
    from bifrost.modules.citations import next_sequential_id
    # continues from the max, never refills gaps
    assert next_sequential_id("C", {"C0001", "C0036", "C0068"}) == "C0069"
    # legacy N_RANDOM ids are ignored when finding the max
    assert next_sequential_id("N", {"N0134", "N_XNH8SH", "N_RX4ZRR"}) == "N0135"
    # empty tree starts at 0001; width grows naturally past 9999
    assert next_sequential_id("R", set()) == "R0001"
    assert next_sequential_id("C", {"C9999"}) == "C10000"
