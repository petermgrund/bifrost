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
        "source_list_entry": "ignored in the note",
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
