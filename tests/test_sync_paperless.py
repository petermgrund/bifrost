"""Unit tests for the pure Paperless sync logic ported from paperless_to_gramps.py."""

from bifrost.modules.sync_paperless import (
    TRANSLATION_DELIMITER,
    build_gramps_date_from_paperless,
    dates_equal,
    format_gramps_date,
    split_transcription,
)


def _doc(created="1947-03-12", doc_id=42):
    return {"id": doc_id, "created": created, "title": "Test doc"}


def test_date_optin_requires_qualifier():
    assert build_gramps_date_from_paperless(_doc(), None) is None


def test_date_exact():
    d = build_gramps_date_from_paperless(_doc(), "Exact")
    assert d["dateval"] == [12, 3, 1947, False]
    assert d["modifier"] == 0 and d["quality"] == 0
    assert format_gramps_date(d) == "1947-03-12"


def test_date_circa():
    d = build_gramps_date_from_paperless(_doc(), "Circa")
    assert d["modifier"] == 3  # ABOUT — full precision kept (unlike Immich)
    assert d["dateval"] == [12, 3, 1947, False]
    assert format_gramps_date(d) == "About 1947-03-12"


def test_date_before_after():
    assert build_gramps_date_from_paperless(_doc(), "Before")["modifier"] == 1
    assert build_gramps_date_from_paperless(_doc(), "After")["modifier"] == 2


def test_date_year_only():
    d = build_gramps_date_from_paperless(_doc(), "Year only")
    assert d["dateval"] == [0, 0, 1947, False]
    assert format_gramps_date(d) == "1947"


def test_date_decade_rounds_down_and_estimates():
    d = build_gramps_date_from_paperless(_doc(), "Decade only")
    assert d["dateval"] == [0, 0, 1940, False]
    assert d["quality"] == 1  # ESTIMATED
    assert format_gramps_date(d) == "Est. 1940"


def test_date_to_from_and_unknown_skip():
    assert build_gramps_date_from_paperless(_doc(), "To/from") is None
    assert build_gramps_date_from_paperless(_doc(), "Sometime") is None


def test_date_missing_created():
    assert build_gramps_date_from_paperless({"id": 1}, "Exact") is None


def test_dates_equal():
    a = {"dateval": [1, 2, 1900, False], "modifier": 0, "quality": 0}
    assert dates_equal(a, dict(a))
    assert not dates_equal(a, {**a, "modifier": 3})
    assert dates_equal(None, {})
    assert not dates_equal(a, None)


def test_split_transcription_no_delimiter():
    assert split_transcription("Kära Maria, ...") == ("Kära Maria, ...", None)


def test_split_transcription_with_translation():
    content = f"Kära Maria\n\n{TRANSLATION_DELIMITER}\n\nDear Maria"
    tx, tl = split_transcription(content)
    assert tx == "Kära Maria"
    assert tl == "Dear Maria"


def test_split_transcription_empty_translation():
    tx, tl = split_transcription(f"Text\n{TRANSLATION_DELIMITER}\n  ")
    assert tx == "Text"
    assert tl is None


def test_clients_follow_redirects():
    """Regression: Gramps 308-redirects POST /objects -> /objects/. httpx must
    follow (requests did by default); otherwise create_media gets the redirect
    HTML body and .json() raises 'Expecting value: line 1 column 1 (char 0)'."""
    from bifrost.core.clients import GrampsClient, PaperlessClient
    g = GrampsClient("http://x/api", "u", "p")
    p = PaperlessClient("http://x", "t")
    assert g._client.follow_redirects
    assert p._client.follow_redirects
