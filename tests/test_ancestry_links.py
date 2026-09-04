import asyncio

from bifrost.core.config import SyncPaperlessConfig
from bifrost.modules import ancestry_links

CFG = SyncPaperlessConfig(gramps_id_field_id=5, source_url_field_id=11, sync_tags=("Sync/Gramps",))
URL = "https://search.ancestry.com/cgi-bin/sse.dll?indiv=1&dbid=1265&h=1620593185"


def _doc(doc_id, url=URL, gid="M00001", title="1841 census"):
    fields = []
    if url is not None:
        fields.append({"field": 11, "value": url})
    if gid is not None:
        fields.append({"field": 5, "value": gid})
    return {"id": doc_id, "title": title, "custom_fields": fields, "tags": []}


class FakePaperless:
    def __init__(self, docs):
        self.docs = docs

    async def list_documents(self, fields=None):
        return list(self.docs)

    async def resolve_tag_id(self, name):
        return 7

    @staticmethod
    def custom_field_value(doc, field_id):
        for f in doc.get("custom_fields") or []:
            if f.get("field") == field_id:
                return f.get("value")
        return None


class FakeGramps:
    def __init__(self, citations, media):
        self.citations = {c["handle"]: c for c in citations}
        self.media = media
        self.updated = []

    async def page_of(self, path, page, page_size=200, **params):
        assert path == "/citations/"
        items = [dict(c) for c in self.citations.values()]
        self.pages = getattr(self, "pages", 0) + 1
        return items[(page - 1) * page_size:page * page_size], len(items)

    async def get_media_by_gramps_id(self, gid):
        return self.media.get(gid)

    async def get_object(self, kind, handle, **params):
        return dict(self.citations[handle])

    async def update_object(self, kind, handle, obj):
        self.citations[handle] = obj
        self.updated.append(handle)


def _cit(handle, gid, apid, media=()):
    return {"handle": handle, "gramps_id": gid,
            "attribute_list": [{"type": "_APID", "value": apid}],
            "media_list": [{"ref": m} for m in media]}


def _events(gen):
    async def collect():
        return [e async for e in gen]
    return asyncio.run(collect())


def test_record_and_apid_keys():
    assert ancestry_links.record_key(URL) == ("1265", "1620593185")
    assert ancestry_links.record_key("https://example.org/?dbid=1&h=2") is None
    assert ancestry_links.record_key(None) is None
    assert ancestry_links.apid_key("1,1265::1620593185") == ("1265", "1620593185")
    assert ancestry_links.apid_key("garbage") is None


def test_scan_lists_missing_links_and_explains_the_rest():
    gr = FakeGramps([_cit("c1", "C1", "1,1265::1620593185"),
                     _cit("c2", "C2", "1,1265::1620593185", media=["h-m1"]),
                     _cit("c3", "C3", "1,9::9")],
                    {"M00001": {"handle": "h-m1", "gramps_id": "M00001"}})
    pl = FakePaperless([_doc(10), _doc(11, url=URL.replace("1620593185", "777"), gid="M00001"),
                        _doc(12, gid=None), _doc(13, url=None, gid="M00002"),
                        _doc(14, gid="GONE")])
    events = _events(ancestry_links.link(gr, pl, CFG, apply=False))
    items = [e for e in events if e.kind == "item"]
    assert [(e.action, e.entity, e.source_id, e.gramps_id) for e in items] == [
        ("failed", "doc", "12", None),
        ("would_update", "citation", "10/c1", "C1"),
        ("failed", "doc", "11", "M00001"),
        ("failed", "doc", "14", "GONE")]
    assert items[0].detail.startswith("no Sync/Gramps tag") and items[0].data == {"reason": "unsynced"}
    assert "re-issued" in items[2].detail
    assert items[1].data["cols"] == {"media": "M00001", "record": "dbid 1265, h 1620593185"}
    assert events[-1].data == {"citations_linked": 0, "in_place": 1, "unmatched": 1,
                               "unsynced": 1, "errors": 1}
    assert gr.updated == []


def test_apply_appends_the_media_ref_once_and_honours_selection():
    gr = FakeGramps([_cit("c1", "C1", "1,1265::1620593185"),
                     _cit("c4", "C4", "1,1265::1620593185")],
                    {"M00001": {"handle": "h-m1", "gramps_id": "M00001"}})
    pl = FakePaperless([_doc(10)])
    events = _events(ancestry_links.link(gr, pl, CFG, apply=True, selected={"citation:10/c1"}))
    assert gr.updated == ["c1"]
    assert gr.citations["c1"]["media_list"] == [ancestry_links.media_ref("h-m1")]
    assert gr.citations["c4"]["media_list"] == []
    assert [e.action for e in events if e.kind == "item"] == ["updated"]
    assert events[-1].data["citations_linked"] == 1
    again = _events(ancestry_links.link(gr, pl, CFG, apply=True))
    assert gr.updated == ["c1", "c4"]
    assert again[-1].data == {"citations_linked": 1, "in_place": 1, "unmatched": 0,
                              "unsynced": 0, "errors": 0}


def test_index_reports_progress_and_is_reused_from_the_cache():
    gr = FakeGramps([_cit("c1", "C1", "1,1265::1620593185")],
                    {"M00001": {"handle": "h-m1", "gramps_id": "M00001"}})
    pl = FakePaperless([_doc(10)])
    cache = {}
    events = _events(ancestry_links.link(gr, pl, CFG, apply=False, cache=cache))
    progress = [(e.detail, e.data["done"], e.data["total"]) for e in events if e.kind == "progress"]
    assert progress == [("Indexing citations", 0, 0), ("Indexing citations", 1, 1), ("Matching records", 1, 1)]
    assert gr.pages == 1 and ancestry_links.INDEX_CACHE_KEY in cache
    _events(ancestry_links.link(gr, pl, CFG, apply=False, cache=cache))
    assert gr.pages == 1


def test_doc_ids_restrict_the_scan():
    gr = FakeGramps([_cit("c1", "C1", "1,1265::1620593185")],
                    {"M00001": {"handle": "h-m1", "gramps_id": "M00001"}})
    pl = FakePaperless([_doc(10), _doc(20, gid=None)])
    events = _events(ancestry_links.link(gr, pl, CFG, apply=False, doc_ids=[10]))
    assert [e.source_id for e in events if e.kind == "item"] == ["10/c1"]


def test_tagged_but_unsynced_doc_says_so():
    gr = FakeGramps([], {})
    doc = _doc(30, gid=None)
    doc["tags"] = [7]
    events = _events(ancestry_links.link(gr, FakePaperless([doc]), CFG, apply=False))
    row = [e for e in events if e.kind == "item"][0]
    assert row.detail.startswith("tagged Sync/Gramps but not synced")
