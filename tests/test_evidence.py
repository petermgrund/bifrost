import asyncio

import pytest
import yaml

from bifrost.core.config import ConfigError, EvidenceConfig, load_config, parse_evidence
from bifrost.modules import evidence as ev

CFG = EvidenceConfig(enabled=True)


# --- builders mirroring what the Gramps Web API returns ---

def attr(t, v):
    return {"type": t, "value": v, "private": False}


def cit(gid, page=None, conf=4, source="S1", attrs=(), notes=(), media=(), links=None, change=100):
    """A citation; its page string is unique unless given, so citations are not read as siblings"""
    return {"handle": gid, "gramps_id": gid, "page": f"p. {gid}" if page is None else page,
            "confidence": conf, "source_handle": source,
            "attribute_list": [attr(t, v) for t, v in attrs], "note_list": list(notes),
            "media_list": [{"ref": m} for m in media], "backlinks": links or {}, "change": change, "tag_list": []}


def event(gid, type="Birth", cits=(), notes=(), tags=(), sortval=0, when="", place="", desc="", attrs=()):
    return {"handle": gid, "gramps_id": gid, "type": type, "citation_list": list(cits), "note_list": list(notes),
            "tag_list": list(tags), "date": {"sortval": sortval, "text": when},
            "profile": {"date": when, "place": place}, "description": desc,
            "attribute_list": [{"type": t, "value": v, "citation_list": list(c)} for t, v, c in attrs], "change": 100}


def person(gid, name="Persson, Per", events=(), families=(), parents=(), cits=(), name_cits=(), notes=(), tags=(),
           birth="", death=""):
    return {"handle": gid, "gramps_id": gid,
            "profile": {"name_display": name, "birth": {"date": birth}, "death": {"date": death}},
            "primary_name": {"citation_list": list(name_cits), "first_name": "", "surname_list": []},
            "alternate_names": [], "event_ref_list": [{"ref": e, "role": r} for e, r in events],
            "family_list": list(families), "parent_family_list": list(parents), "citation_list": list(cits),
            "note_list": list(notes), "tag_list": list(tags), "attribute_list": []}


def family(gid, father=None, mother=None, children=(), cits=(), events=(), notes=(), tags=()):
    return {"handle": gid, "gramps_id": gid, "father_handle": father, "mother_handle": mother,
            "child_ref_list": [{"ref": h, "citation_list": list(c), "note_list": []} for h, c in children],
            "event_ref_list": [{"ref": e, "role": "Family"} for e in events], "citation_list": list(cits),
            "note_list": list(notes), "tag_list": list(tags), "attribute_list": []}


def source(gid, title="Norra Ny C:4 (1773-1825)", abbrev="", stype=None):
    return {"handle": gid, "gramps_id": gid, "title": title, "abbrev": abbrev,
            "attribute_list": [attr("Source type", stype)] if stype else []}


def note(h, type="Report", text="The argument.", change=100):
    return {"handle": h, "gramps_id": h, "type": type, "text": {"string": text}, "change": change}


def tree(citations=(), events=(), people=(), families=(), sources=(), notes=(), tags=None):
    t = ev.Tree(citations={c["handle"]: c for c in citations}, events={e["handle"]: e for e in events},
                people={p["handle"]: p for p in people}, families={f["handle"]: f for f in families},
                sources={s["handle"]: s for s in sources}, notes={n["handle"]: n for n in notes},
                tags=dict(tags or {}), loaded_at=1.0)
    t.index()
    return t


def per_tree():
    """Per: a Birth (C1), a Death with a fresh Report note (C2 complete, C3 Normal and newer than the
    note), a family with Marit and a Marriage from a derivative source (C4), parents (C5 on the child
    reference), an identity citation (C6) and a name citation (C7)"""
    return tree(
        citations=[
            cit("C1", attrs=[("Cited for", "birth")], links={"event": ["E1"]}),
            cit("C2", attrs=[("Cited for", "death"), ("Evidence", "death: direct")], notes=["N3"],
                links={"event": ["E2"]}),
            cit("C3", page="pp. 203-205 (images 104-106)", conf=2, attrs=[("Cited for", "death")],
                links={"event": ["E2"]}, change=200),
            cit("C4", conf=3, source="S2", attrs=[("Cited for", "marriage"),
                                                  ("Evidence", "marriage: direct; register entry")],
                links={"event": ["E3"]}),
            cit("C5", attrs=[("Cited for", "mother")], links={"family": ["F0"]}),
            cit("C6", attrs=[("Cited for", "identity")], links={"person": ["P1"]}),
            cit("C7", attrs=[("Cited for", "name")], links={"person": ["P1"]}),
        ],
        events=[event("E1", "Birth", cits=["C1"], sortval=10, when="1773"),
                event("E2", "Death", cits=["C2", "C3"], notes=["N1", "N2"], sortval=30, when="1832-05-03",
                      place="Norra Ny"),
                event("E3", "Marriage", cits=["C4"], sortval=20, when="1806-04-07"),
                event("E9", "Residence", sortval=15)],
        people=[person("P1", events=[("E1", "Primary"), ("E2", "Primary"), ("E9", "Primary")], families=["F1"],
                       parents=["F0"], cits=["C6"], name_cits=["C7"], birth="1773", death="1832"),
                person("P2", "Olofsdotter, Marit", families=["F1"]),
                person("P3", "Olsson, Per"), person("P4", "Nilsdotter, Karin")],
        families=[family("F1", "P1", "P2", events=["E3"]),
                  family("F0", "P3", "P4", children=[("P1", ["C5"])])],
        sources=[source("S1", stype="original"), source("S2", "Compiled index", stype="derivative")],
        notes=[note("N1", "Report", "Died 3 May 1832.", change=150), note("N2", "To Do", "Find the burial."),
               note("N3", "Abstract", "Per Persson died 3 May 1832, aged 59.")],
    )


# --- reading one citation ---

class TestParsing:
    def test_split_values(self):
        assert ev.split_values(" birth date, Birth Location;baptism ") == ["birth date", "birth location", "baptism"]
        assert ev.split_values(None) == []

    def test_cited_for_rows_and_words(self):
        c = cit("C", attrs=[("Cited for", "birth, baptism"), ("Cited for", "mother")])
        assert ev.cited_for(c) == [{"raw": "birth, baptism", "words": ["birth", "baptism"]},
                                   {"raw": "mother", "words": ["mother"]}]
        assert ev.cited_words(c) == ["birth", "baptism", "mother"]

    def test_evidence_rows(self):
        c = cit("C", attrs=[("Evidence", "Birth: Indirect; aged 45 on 6 Aug 1810"),
                            ("Evidence", "residence: negative"),
                            ("Evidence", "stated age 14, birth year inferred")])
        rows = ev.evidence_rows(c)
        assert rows[0] == {"raw": "Birth: Indirect; aged 45 on 6 Aug 1810", "ok": True, "word": "birth",
                           "cls": "indirect", "why": "aged 45 on 6 Aug 1810"}
        assert rows[1]["ok"] and rows[1]["cls"] == "negative" and rows[1]["why"] == ""
        assert rows[2]["ok"] is False and rows[2]["why"] == "stated age 14, birth year inferred"

    @pytest.mark.parametrize("text", [
        "image 496", "images 104-106", "image 496, right", "pp. 563-656", "PDF p. 1", "slide 100",
        "Fold3 page 45", "serial 1083", "certified copy p. 135", "unikt id 114962", "1904-1965", "1871–1875",
        "1883", "b. 18 Dec 1898, bapt. 20 Jun 1915", "d. 1948", "Michele b. 1888", "senior", "AP-29",
        "T. 156 N., R. 47 W.", "",
    ])
    def test_parenthetical_allowed(self, text):
        assert ev.parenthetical_allowed(text)

    @pytest.mark.parametrize("text", [
        "entry for Edmund G Grund", "mother named", "servant, stated birth year 1856", "death date",
        "witness at Jeppe Mauritz Olsson's naturalization", "year given as 1887, in error for 1877",
        "b. 28 Dec 1855, daughter", "lodger", "copy",
    ])
    def test_parenthetical_flagged(self, text):
        assert not ev.parenthetical_allowed(text)

    def test_stray_parentheticals(self):
        assert ev.stray_parentheticals("p. 425 (image 218), Per Persson household (family relationships)") == \
            ["family relationships"]
        assert ev.stray_parentheticals(None) == []

    def test_source_type_and_ceiling(self):
        t = tree(citations=[cit("C", source="S2"), cit("D", source="S1"), cit("E", source="S9")],
                 sources=[source("S1"), source("S2", stype=" Derivative ")])
        assert ev.source_type(t, t.citations["C"]) == "derivative"
        assert ev.source_type(t, t.citations["D"]) is None
        assert ev.source_type(t, t.citations["E"]) is None
        assert ev.confidence_ceiling("derivative") == 3
        assert ev.confidence_ceiling("authored") == 2
        assert ev.confidence_ceiling(None) is None


class TestAttachments:
    def test_each_slot_is_told_apart(self):
        t = tree(
            citations=[cit("C", links={"event": ["E1", "E2"], "family": ["F1", "F2"], "person": ["P1", "P2"],
                                       "media": ["M1"], "note": ["N1"]})],
            events=[event("E1", cits=["C"]), event("E2", "Birth", attrs=[("Information origin", "place", ["C"])])],
            people=[person("P1", "Persson, Per", events=[("E1", "Primary")], cits=["C"]),
                    person("P2", "Olofsdotter, Marit", name_cits=["C"])],
            families=[family("F1", "P1", "P2", cits=["C"]), family("F2", "P1", "P2", children=[("P1", ["C"])])],
        )
        atts = ev.attachments(t, t.citations["C"])
        assert [(a["kind"], a["handle"]) for a in atts] == [
            ("event", "E1"), ("eventattr", "E2"), ("family", "F1"), ("childref", "F2"), ("person", "P1"),
            ("name", "P2"), ("media", "M1")]
        assert atts[0]["title"] == "Birth of Persson, Per"
        assert atts[3]["title"] == "Persson, Per, child of Persson, Per & Olofsdotter, Marit"
        assert atts[3]["child"] == "P1"

    def test_words_for_each_kind(self):
        assert ev.words_for(CFG, "event", "Birth") == {"birth", "birthplace", "age"}
        assert ev.words_for(CFG, "eventattr", "Probate") == {"probate", "inventory", "will"}
        assert ev.words_for(CFG, "event", "Retirement") == {"retirement"}
        assert ev.words_for(CFG, "family") == {"spouse", "marriage"}
        assert ev.words_for(CFG, "childref") == {"mother", "father", "parents", "child"}
        assert ev.words_for(CFG, "person") == {"identity"}
        assert ev.words_for(CFG, "name") == {"name"}
        assert ev.words_for(CFG, "place") == {"place"}
        assert ev.words_for(CFG, "unknown") == set()


# --- claims and proofs ---

class TestClaims:
    def test_claims_for_person_in_order(self):
        t = per_tree()
        claims = ev.claims_for_person(t, "P1")
        assert [c["id"] for c in claims] == [
            "event:E1", "event:E9", "event:E3", "event:E2", "family:F1", "childref:F0:P1", "person:P1", "name:P1"]
        by_id = {c["id"]: c for c in claims}
        assert by_id["event:E1"]["title"] == "Birth" and by_id["event:E1"]["when"]["date"] == "1773"
        assert by_id["event:E3"]["title"] == "Marriage with Olofsdotter, Marit"
        assert by_id["family:F1"]["title"] == "Family with Olofsdotter, Marit"
        assert by_id["childref:F0:P1"]["title"] == "Child of Olsson, Per & Nilsdotter, Karin"
        assert by_id["childref:F0:P1"]["citations"] == ["C5"]
        assert by_id["person:P1"]["citations"] == ["C6"]
        assert by_id["name:P1"]["citations"] == ["C7"]
        assert all(c["person"] == "P1" for c in claims)

    def test_unknown_person_has_no_claims(self):
        assert ev.claims_for_person(per_tree(), "nobody") == []

    @pytest.mark.parametrize("claim_id,title", [
        ("event:E2", "Death"), ("family:F1", "Persson, Per & Olofsdotter, Marit"),
        ("childref:F0:P1", "Child of Olsson, Per & Nilsdotter, Karin"), ("person:P1", "Identity"),
        ("name:P1", "Name"), ("event:E3", "Marriage with Olofsdotter, Marit"),
    ])
    def test_claim_by_id(self, claim_id, title):
        found = ev.claim_by_id(per_tree(), claim_id)
        assert found and found["id"] == claim_id and found["title"] == title

    @pytest.mark.parametrize("claim_id", ["event:E99", "family:F9", "childref:F0:P9", "person:P9", "bogus", "event"])
    def test_claim_by_id_misses(self, claim_id):
        assert ev.claim_by_id(per_tree(), claim_id) is None

    def test_event_with_no_person_still_resolves(self):
        t = tree(events=[event("E5", "Census", cits=[])])
        found = ev.claim_by_id(t, "event:E5")
        assert found["title"] == "Census" and found["person"] is None


class TestProof:
    def test_rows_matched_and_classified(self):
        t = per_tree()
        p = ev.proof(t, CFG, ev.claim_by_id(t, "event:E2"), "https://g")
        assert p["url"] == "https://g/event/E2"
        assert [r["gramps_id"] for r in p["rows"]] == ["C2", "C3"]       # highest confidence first
        c2, c3 = p["rows"]
        assert c2["matched"] == ["death"] and c2["complete"] and c2["url"] == "https://g/citation/C2"
        assert c2["abstract"] == "Per Persson died 3 May 1832, aged 59."
        assert c2["source"] == {"gramps_id": "S1", "title": "Norra Ny C:4 (1773-1825)", "abbrev": "",
                                "type": "original", "url": "https://g/source/S1"}
        assert c3["needs_evidence"] and c3["missing"] == ["Evidence line needed (confidence below High)"]
        assert p["report"]["text"] == "Died 3 May 1832." and p["todo"]["text"] == "Find the burial."
        assert p["needs_review"] == ["C3"]
        assert p["complete"] is False
        assert p["missing"] == ["C3: Evidence line needed (confidence below High)", "Report note older than C3"]
        assert p["fits"] == ["death"]
        assert p["stated"] == []

    def test_complete_claim(self):
        t = per_tree()
        t.citations["C3"]["change"] = 120
        t.citations["C3"]["attribute_list"].append(attr("Evidence", "death: indirect; states 3 May 1832 in the inventory"))
        p = ev.proof(t, CFG, ev.claim_by_id(t, "event:E2"))
        assert p["complete"] and p["missing"] == [] and p["needs_review"] == []
        assert p["stated"] == [{"citation": "C3", "cls": "indirect", "why": "states 3 May 1832 in the inventory"}]

    def test_derivative_source_needs_evidence_even_at_high(self):
        t = per_tree()
        p = ev.proof(t, CFG, ev.claim_by_id(t, "event:E3"))
        row = p["rows"][0]
        assert row["needs_evidence"] and row["evidence_for_claim"][0]["why"] == "register entry" and row["complete"]
        t.citations["C4"]["attribute_list"] = [attr("Cited for", "marriage")]
        row = ev.proof(t, CFG, ev.claim_by_id(t, "event:E3"))["rows"][0]
        assert row["missing"] == ["Evidence line needed (source is derivative)"]

    def test_word_that_does_not_fit_and_bad_evidence(self):
        t = per_tree()
        t.citations["C1"]["attribute_list"] = [attr("Cited for", "residence"), attr("Evidence", "nonsense")]
        row = ev.proof(t, CFG, ev.claim_by_id(t, "event:E1"))["rows"][0]
        assert row["matched"] == [] and row["missing"] == ["no Cited for word fits this claim", "Evidence row not in shape"]
        t.citations["C1"]["attribute_list"] = []
        row = ev.proof(t, CFG, ev.claim_by_id(t, "event:E1"))["rows"][0]
        assert row["missing"] == ["no Cited for row"]

    def test_no_citation_and_no_report(self):
        t = per_tree()
        p = ev.proof(t, CFG, ev.claim_by_id(t, "event:E9"))
        assert p["missing"] == ["no citation attached"] and p["rows"] == []
        p = ev.proof(t, CFG, ev.claim_by_id(t, "event:E1"))
        assert p["missing"] == ["no Report note"]

    def test_status_tags_are_the_configured_ones(self):
        t = per_tree()
        t.tags = {"T1": "Unproven", "T2": "Sweden"}
        t.events["E1"]["tag_list"] = ["T1", "T2"]
        p = ev.proof(t, CFG, ev.claim_by_id(t, "event:E1"))
        assert p["tags"] == ["Unproven", "Sweden"] and p["status"] == ["Unproven"]


class TestPerson:
    def test_summary_claims_and_stars(self):
        t = per_tree()
        t.citations["C3"]["change"] = 120
        t.citations["C3"]["attribute_list"].append(attr("Evidence", "death: indirect"))
        s = ev.person_summary(t, CFG, "P1", "https://g")
        assert s["name"] == "Persson, Per" and s["years"] == "1773–1832" and s["url"] == "https://g/person/P1"
        assert s["citations"] == 7
        death = next(c for c in s["claims"] if c["id"] == "event:E2")
        assert death["citations"] == 2 and death["rows_complete"] == 2 and death["report"] and death["complete"]
        assert s["stars"] == {"birth": 0.0, "marriage": 0.0, "death": 1.0, "burial": 0.0, "parents": 0.0}

    def test_star_needs_no_status_tag(self):
        t = per_tree()
        t.citations["C3"]["change"] = 120
        t.citations["C3"]["attribute_list"].append(attr("Evidence", "death: indirect"))
        t.tags = {"T1": "Conflict"}
        t.events["E2"]["tag_list"] = ["T1"]
        assert ev.person_summary(t, CFG, "P1")["stars"]["death"] == 0.0

    def test_people_sorted_by_name(self):
        t = per_tree()
        rows = ev.people(t)
        assert [r["name"] for r in rows] == ["Nilsdotter, Karin", "Olofsdotter, Marit", "Olsson, Per", "Persson, Per"]
        assert rows[3]["years"] == "1773–1832" and rows[0]["years"] == ""

    def test_unknown_person(self):
        assert ev.person_summary(per_tree(), CFG, "P9") is None

    def test_name_without_surname(self):
        t = tree(people=[person("P1", ", Else")])
        assert ev.person_name(t, "P1") == "Else"

    def test_years_from_fuzzy_dates(self):
        t = tree(people=[person("P1", birth="about 1850", death="before 1920-03"),
                         person("P2", birth="1773"), person("P3", death="calculated 1899")])
        assert ev.person_years(t, "P1") == "1850–1920"
        assert ev.person_years(t, "P2") == "1773–…"
        assert ev.person_years(t, "P3") == "…–1899"


# --- audits ---

def found(t, cfg=CFG, public_url=""):
    return {c["id"]: c["items"] for c in ev.audits(t, cfg, public_url)["checks"]}


def only(items, *ids):
    """The checks with findings are exactly these"""
    return {k for k, v in items.items() if v} == set(ids)


class TestAudits:
    def test_clean_tree_has_no_findings(self):
        t = per_tree()
        t.citations["C3"]["change"] = 120
        t.citations["C3"]["attribute_list"].append(attr("Evidence", "death: indirect"))
        a = ev.audits(t, CFG)
        assert a["findings"] == 0 and a["citations"] == 7
        assert a["tags_missing"] == ["Conflict", "Disproven", "Lapse", "Unproven"] and a["tags_present"] == []
        assert [c["id"] for c in a["checks"]] == [cid for cid, _t, _w in ev.CHECKS]

    def test_per_tree_as_built(self):
        items = found(per_tree())
        assert only(items, "evidence_missing", "needs_review")
        assert items["evidence_missing"][0]["detail"] == "death: Normal, original source"
        assert items["needs_review"][0] == {"object": "event", "gramps_id": "E2", "title": "Death of Persson, Per",
                                            "detail": "changed: C3", "url": None}

    def test_unattached_and_no_cited_for(self):
        t = tree(citations=[cit("C1"), cit("C2", links={"event": ["E1"]})],
                 events=[event("E1", cits=["C2"])], people=[person("P1", events=[("E1", "Primary")])])
        items = found(t, public_url="https://g")
        assert only(items, "unattached", "no_cited_for")
        assert items["unattached"][0]["gramps_id"] == "C1" and items["unattached"][0]["url"] == "https://g/citation/C1"
        assert items["no_cited_for"][0]["detail"] == "attached to Birth of Persson, Per"

    def test_words_rows_and_attachments(self):
        t = tree(citations=[cit("C1", attrs=[("Cited for", "birth, foo"), ("Cited for", "residence")],
                                links={"event": ["E1"]})],
                 events=[event("E1", cits=["C1"])], people=[person("P1", events=[("E1", "Primary")])])
        items = found(t)
        assert only(items, "several_in_one", "word_unknown", "row_unmatched")
        assert items["several_in_one"][0]["detail"] == "Cited for: birth, foo"
        assert items["word_unknown"][0]["detail"] == "Cited for: foo"
        assert items["row_unmatched"][0]["detail"] == "Cited for: residence, attached to Birth of Persson, Per"

    def test_attachment_unmatched(self):
        t = tree(citations=[cit("C1", attrs=[("Cited for", "birth")], links={"event": ["E1"], "family": ["F1"]})],
                 events=[event("E1", cits=["C1"])], people=[person("P1", events=[("E1", "Primary")], families=["F1"])],
                 families=[family("F1", "P1", cits=["C1"])])
        items = found(t)
        assert only(items, "attachment_unmatched")
        assert items["attachment_unmatched"][0]["detail"] == "attached to Persson, Per (family); Cited for: birth"

    def test_evidence_rows(self):
        t = tree(citations=[cit("C1", conf=1, attrs=[("Cited for", "birth"), ("Evidence", "birth indirect"),
                                                     ("Evidence", "death: direct")], links={"event": ["E1"]})],
                 events=[event("E1", cits=["C1"])], people=[person("P1", events=[("E1", "Primary")])])
        items = found(t)
        assert only(items, "evidence_missing", "evidence_unparsed")
        assert [i["detail"] for i in items["evidence_unparsed"]] == [
            "Evidence: birth indirect", "Evidence names 'death', which no Cited for row holds"]
        assert items["evidence_missing"][0]["detail"] == "birth: Low"

    def test_page_url_attributes_and_ceiling(self):
        t = tree(citations=[cit("C1", page="p. 5 (image 6), Per Persson household (family relationships)",
                                attrs=[("Cited for", "residence"), ("Record URL", "https://x"), ("Pinpoint", "ABC.L1")],
                                media=["M1"], source="S2", links={"event": ["E1"]})],
                 events=[event("E1", "Residence", cits=["C1"])], people=[person("P1", events=[("E1", "Primary")])],
                 sources=[source("S2", stype="authored")])
        items = found(t)
        assert only(items, "page_parenthetical", "record_url_with_media", "attribute_unknown", "confidence_ceiling",
                    "evidence_missing")
        assert items["page_parenthetical"][0]["detail"] == "(family relationships)"
        assert items["attribute_unknown"][0]["detail"] == "Pinpoint: ABC.L1"
        assert items["confidence_ceiling"][0]["detail"] == "Very High on a authored source"
        assert items["evidence_missing"][0]["detail"] == "residence: Very High, authored source"

    def test_siblings(self):
        t = tree(citations=[cit("C1", page="pp. 203-205", attrs=[("Cited for", "death")], media=["M1"], notes=["N1"],
                                links={"event": ["E1"]}),
                            cit("C2", page="pp.  203-205", conf=4, attrs=[("Cited for", "death")], media=["M2"],
                                links={"event": ["E1"]})],
                 events=[event("E1", "Death", cits=["C1", "C2"], notes=["N2"])],
                 people=[person("P1", events=[("E1", "Primary")])], notes=[note("N1", "Abstract"), note("N2")])
        items = found(t)
        assert only(items, "sibling_mismatch")
        assert [i["detail"] for i in items["sibling_mismatch"]] == [
            "C1, C2: different media", "C1, C2: different notes", "C1, C2: same confidence, merge them"]

    def test_unproven_high_and_no_proof(self):
        t = tree(citations=[cit("C1", attrs=[("Cited for", "birth")], links={"event": ["E1"]}),
                            cit("C2", attrs=[("Cited for", "birth")], links={"event": ["E1"]})],
                 events=[event("E1", cits=["C1", "C2"], tags=["T1"])],
                 people=[person("P1", events=[("E1", "Primary")])], tags={"T1": "Unproven"})
        items = found(t)
        assert only(items, "unproven_high", "no_proof")
        assert items["unproven_high"][0]["detail"] == "C1, C2"
        assert items["no_proof"][0] == {"object": "event", "gramps_id": "E1", "title": "Birth of Persson, Per",
                                        "detail": "2 citations", "url": None}
        assert ev.audits(t, CFG)["tags_present"] == ["Unproven"]

    def test_a_shared_event_is_checked_once(self):
        t = tree(citations=[cit("C1", attrs=[("Cited for", "marriage")], links={"event": ["E1"]}),
                            cit("C2", attrs=[("Cited for", "marriage")], links={"event": ["E1"]})],
                 events=[event("E1", "Marriage", cits=["C1", "C2"])],
                 people=[person("P1", events=[("E1", "Family")], families=["F1"]),
                         person("P2", "Olofsdotter, Marit", events=[("E1", "Family")], families=["F1"])],
                 families=[family("F1", "P1", "P2", events=["E1"])])
        assert len(found(t)["no_proof"]) == 1


# --- loading ---

class FakeGramps:
    def __init__(self):
        self.calls = []

    async def list_objects(self, api_path, keys=None, **params):
        self.calls.append((api_path, keys, params))
        return {
            "citations": [cit("C1", links={"event": ["E1"]})],
            "events": [event("E1", cits=["C1"])],
            "people": [person("P1", events=[("E1", "Primary")], families=["F1"])],
            "families": [family("F1", "P1", events=["E1"])],
            "sources": [source("S1")],
            "notes": [note("N1")],
            "tags": [{"handle": "T1", "name": "Unproven"}],
        }[api_path]


def test_load_tree_reads_everything_once_and_indexes():
    g = FakeGramps()
    t = asyncio.run(ev.load_tree(g))
    assert [c[0] for c in g.calls] == ["citations", "events", "people", "families", "sources", "notes", "tags"]
    assert g.calls[0][2] == {"backlinks": "true"}
    assert g.calls[1][2] == {"profile": "self", "locale": "en"} and "profile" in g.calls[1][1]
    assert g.calls[2][2] == {"profile": "self", "locale": "en"}
    assert t.event_people == {"E1": [("P1", "Primary")]} and t.event_families == {"E1": ["F1"]}
    assert t.by_gramps_id["citation"] == {"C1": "C1"} and t.tags == {"T1": "Unproven"}
    assert t.loaded_at > 0


# --- config ---

class TestConfig:
    def test_defaults(self):
        c = parse_evidence(None)
        assert c.enabled is False and "birth" in c.cited_for and c.tag("disproven") == "Disproven"
        assert dict(c.claim_words)["Birth"] == ("birth", "birthplace", "age")

    def test_overrides(self):
        c = parse_evidence({"enabled": True, "cited_for": ["Birth", "death", "inventory"],
                            "claim_words": {"Probate": ["inventory"]}, "tags": {"lapse": "Gap"}})
        assert c.enabled and c.cited_for == ("birth", "death", "inventory")
        assert c.claim_words == (("Probate", ("inventory",)),) and c.tag("lapse") == "Gap" and c.tag("unproven") == "Unproven"

    @pytest.mark.parametrize("block,message", [
        ({"claim_words": {"Probate": ["inventory"]}, "cited_for": ["birth"]}, "not in evidence.cited_for"),
        ({"cited_for": ["birth, death"]}, "not a single word"),
        ({"claim_words": ["x"]}, "must map event types"),
        ({"tags": {"proven": "Proven"}}, "unknown status"),
        ({"tags": {"lapse": ""}}, "needs a tag name"),
        ({"tags": {"lapse": "Unproven"}}, "share a tag name"),
        ("yes", "must be a mapping"),
    ])
    def test_refusals(self, block, message):
        with pytest.raises(ConfigError, match=message):
            parse_evidence(block)

    def test_load_config_reads_the_block(self, tmp_path):
        path = tmp_path / "config.yaml"
        path.write_text(yaml.safe_dump({
            "gramps": {"base_url": "http://g/api", "username": "u", "password": "p"},
            "paperless": {"base_url": "http://p", "api_token": "t"},
            "evidence": {"enabled": True, "tags": {"conflict": "Disagrees"}},
        }))
        cfg = load_config(path)
        assert cfg.evidence.enabled and cfg.evidence.tag("conflict") == "Disagrees"
        path.write_text(yaml.safe_dump({
            "gramps": {"base_url": "http://g/api", "username": "u", "password": "p"},
            "paperless": {"base_url": "http://p", "api_token": "t"}}))
        assert load_config(path).evidence == EvidenceConfig()
