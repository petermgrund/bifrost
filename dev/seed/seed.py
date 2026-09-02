#!/usr/bin/env python3
"""Seed"""

from __future__ import annotations

import argparse
import datetime as dt
import mimetypes
import os
import re
import secrets
import sys
import time
from pathlib import Path

import httpx
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import samples  # noqa: E402

DEV = Path(__file__).resolve().parents[1]
PASSWORD = os.environ.get("DEV_PASSWORD", "bifrost-dev")
CONFIG_OUT = Path(os.environ.get("BIFROST_CONFIG") or DEV / "config.yaml")
GENERATED = DEV / "data" / "samples"

URLS = {
    "gramps": os.environ.get("GRAMPS_URL", "http://grampsweb:5000"),
    "paperless": os.environ.get("PAPERLESS_URL", "http://paperless:8000"),
    "immich": os.environ.get("IMMICH_URL", "http://immich-server:2283"),
}
PUBLIC = {
    "gramps": os.environ.get("GRAMPS_PUBLIC_URL", "http://localhost:5555"),
    "paperless": os.environ.get("PAPERLESS_PUBLIC_URL", "http://localhost:8000"),
    "immich": os.environ.get("IMMICH_PUBLIC_URL", "http://localhost:2283"),
}

GRAMPS_USER = "owner"
PAPERLESS_USER = "admin"
IMMICH_OWNER = ("owner@bifrost.dev", "Dev Owner")
IMMICH_PARTNER = ("partner@bifrost.dev", "Dev Partner")

PLACE_TAG = "Bifrost Place"
SKIP_TITLE_TAG = "skip-title-sync"
IMMICH_TAGS = ["Sync/Gramps", "Sync/Date", "Sync/Location", "Sync/Description",
               "Sync/ManualFaces", "Date/Approximate", "Date/Before", "Date/After",
               "Date/Estimated", "Date/Calculated", "Date/Year", "Date/Month", "ID"]
PAPERLESS_TAGS = ["doc", "img", "transcription", "Gemini OCR"]
DATE_QUALIFIERS = ["Exact", "Circa", "Before", "After", "Year only", "Decade only"]
PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".tif", ".tiff"}

NOW = int(time.time())


def log(msg: str) -> None:
    print(f"[seed] {msg}", flush=True)


def die(msg: str) -> None:
    print(f"[seed] ERROR: {msg}", file=sys.stderr, flush=True)
    sys.exit(1)


def wait_for(label: str, probe, timeout: int = 600) -> None:
    t0, last = time.time(), ""
    while True:
        try:
            if probe():
                log(f"{label}: reachable")
                return
        except Exception as exc:  # noqa: BLE001
            last = f"{type(exc).__name__}: {str(exc)[:120]}"
        if time.time() - t0 > timeout:
            die(f"{label} not reachable after {timeout}s ({last})")
        time.sleep(3)


# ------------------------------------------------------------------- Gramps

def handle() -> str:
    return secrets.token_hex(8)


def gdate(year: int, month: int = 0, day: int = 0, modifier: int = 0, quality: int = 0) -> dict:
    """A Gramps Date with its sort value (the Julian day of the date)"""
    y, m, d = max(year, 1), max(month, 1), max(day, 1)
    a = (14 - m) // 12
    yy, mm = y + 4800 - a, m + 12 * a - 3
    sdn = d + (153 * mm + 2) // 5 + 365 * yy + yy // 4 - yy // 100 + yy // 400 - 32045
    return {"_class": "Date", "calendar": 0, "modifier": modifier, "quality": quality,
            "dateval": [day, month, year, False], "text": "", "sortval": sdn, "newyear": 0}


ABOUT = 3


class Tree:
    """Builds the object list for one POST /api/objects/ call"""

    def __init__(self, place_tag: str) -> None:
        self.objects: list[dict] = []
        self.counters: dict[str, int] = {}
        self.places: dict[str, str] = {}
        self.place_tag = place_tag

    def gid(self, prefix: str) -> str:
        n = self.counters.get(prefix, 9000) + 1
        self.counters[prefix] = n
        return f"{prefix}{n:04d}"

    def add(self, obj: dict) -> str:
        obj.setdefault("change", NOW)
        obj.setdefault("private", False)
        self.objects.append(obj)
        return obj["handle"]

    def place(self, name: str, ptype: str, parent: str | None = None,
              coords: tuple[float, float] | None = None, title: str | None = None,
              osm_relation: int | None = None) -> str:
        h = handle()
        obj = {"_class": "Place", "handle": h, "gramps_id": self.gid("P"),
               "name": {"_class": "PlaceName", "value": name}, "place_type": ptype,
               "title": title or name,
               "placeref_list": [{"_class": "PlaceRef", "ref": parent}] if parent else [],
               "lat": f"{coords[0]:.6f}" if coords else "",
               "long": f"{coords[1]:.6f}" if coords else "",
               "tag_list": [self.place_tag] if coords else []}
        if osm_relation:
            obj["urls"] = [{"_class": "Url", "type": "OSM URL", "desc": "",
                            "path": f"https://www.openstreetmap.org/relation/{osm_relation}",
                            "private": False}]
        self.places[name] = h
        return self.add(obj)

    def event(self, etype: str, date: dict | None = None, place: str | None = None,
              description: str = "", citations: tuple[str, ...] = ()) -> str:
        obj = {"_class": "Event", "handle": handle(), "gramps_id": self.gid("E"), "type": etype,
               "description": description, "citation_list": list(citations)}
        if date:
            obj["date"] = date
        if place:
            obj["place"] = place
        return self.add(obj)

    @staticmethod
    def name(first: str, surname: str, ntype: str = "Birth Name") -> dict:
        return {"_class": "Name", "first_name": first, "type": ntype,
                "surname_list": [{"_class": "Surname", "surname": surname, "primary": True}]}

    def person(self, first: str, surname: str, gender: int, events: list[str],
               alt_names: list[dict] | None = None, notes: list[str] | None = None,
               name_type: str = "Birth Name") -> str:
        obj = {"_class": "Person", "handle": handle(), "gramps_id": self.gid("I"), "gender": gender,
               "primary_name": self.name(first, surname, name_type),
               "alternate_names": alt_names or [],
               "event_ref_list": [{"_class": "EventRef", "ref": e, "role": "Primary"} for e in events],
               "birth_ref_index": 0, "death_ref_index": 1,
               "family_list": [], "parent_family_list": [], "note_list": notes or [], "tag_list": []}
        return self.add(obj)

    def family(self, father: str, mother: str, children: list[str], marriage: str) -> str:
        h = handle()
        self.add({"_class": "Family", "handle": h, "gramps_id": self.gid("F"),
                  "father_handle": father, "mother_handle": mother, "type": "Married",
                  "child_ref_list": [{"_class": "ChildRef", "ref": c, "frel": "Birth", "mrel": "Birth"}
                                     for c in children],
                  "event_ref_list": [{"_class": "EventRef", "ref": marriage, "role": "Family"}]})
        by_handle = {o["handle"]: o for o in self.objects}
        for p in (father, mother):
            by_handle[p]["family_list"].append(h)
        for c in children:
            by_handle[c]["parent_family_list"].append(h)
        return h

    def repository(self, name: str, rtype: str = "Archive") -> str:
        return self.add({"_class": "Repository", "handle": handle(), "gramps_id": self.gid("R"),
                         "type": rtype, "name": name})

    def source(self, title: str, author: str, pubinfo: str, repo: str, call_number: str) -> str:
        return self.add({"_class": "Source", "handle": handle(), "gramps_id": self.gid("S"),
                         "title": title, "author": author, "pubinfo": pubinfo, "abbrev": "",
                         "reporef_list": [{"_class": "RepoRef", "ref": repo, "call_number": call_number,
                                           "media_type": "Microfilm"}]})

    def citation(self, source: str, page: str, confidence: int = 2, date: dict | None = None) -> str:
        obj = {"_class": "Citation", "handle": handle(), "gramps_id": self.gid("C"),
               "source_handle": source, "page": page, "confidence": confidence}
        if date:
            obj["date"] = date
        return self.add(obj)

    def note(self, text: str, ntype: str = "Person Note") -> str:
        return self.add({"_class": "Note", "handle": handle(), "gramps_id": self.gid("N"),
                         "text": {"_class": "StyledText", "string": text, "tags": []},
                         "type": ntype, "format": 0})


def build_tree(place_tag: str) -> Tree:
    t = Tree(place_tag)
    P = samples.PLACES
    sweden = t.place("Sweden", "Country")
    kalmar = t.place("Kalmar län", "County", sweden, title="Kalmar län, Sweden")
    vimmerby = t.place("Vimmerby", "City", kalmar, P["Vimmerby"], "Vimmerby, Kalmar län, Sweden")
    usa = t.place("United States", "Country")
    minnesota = t.place("Minnesota", "State", usa, title="Minnesota, United States")
    chisago = t.place("Chisago County", "County", minnesota, title="Chisago County, Minnesota")
    center_city = t.place("Center City", "Town", chisago, P["Center City"], "Center City, Chisago County, Minnesota")
    farm = t.place("Lindqvist farm", "Farm", chisago, P["Lindqvist farm"], "Lindqvist farm, Chisago County, Minnesota")
    hennepin = t.place("Hennepin County", "County", minnesota, title="Hennepin County, Minnesota")
    minneapolis = t.place("Minneapolis", "City", hennepin, P["Minneapolis"],
                          "Minneapolis, Hennepin County, Minnesota", osm_relation=136712)
    t.place("Foshay Tower", "Building", minneapolis, P["Foshay Tower"], "Foshay Tower, Minneapolis, Minnesota")
    new_york = t.place("New York", "State", usa, title="New York, United States")
    ellis = t.place("Ellis Island", "Locality", new_york, P["Ellis Island"], "Ellis Island, New York")

    mhs = t.repository("Minnesota Historical Society")
    riksarkivet = t.repository("Riksarkivet (Swedish National Archives)")
    census = t.source("1910 United States Federal Census", "U.S. Bureau of the Census",
                      "NARA microfilm publication T624", mhs, "T624, roll 693")
    kyrkbok = t.source("Vimmerby kyrkoarkiv, Födelse- och dopböcker, C:7 (1861-1874)",
                       "Vimmerby församling", "Landsarkivet i Vadstena", riksarkivet, "SE/VALA/00417/C/7")
    c_census = t.citation(census, "Chisago County, Center City Township, ED 47, sheet 4B, "
                                  "dwelling 71, family 73, Anders Lindqvist household",
                          confidence=2, date=gdate(1910, 4, 21))
    c_birth = t.citation(kyrkbok, "1868, no. 23, Anders Johan", confidence=3)

    note_anders = t.note("Anders emigrated from Vimmerby in 1889 and farmed forty acres in Chisago "
                         "County. In the dev stack, Paperless holds his birth record, the 1893 deed "
                         "and the 1910 census page; Immich has the farm photograph from 1923.")

    anders = t.person("Anders Johan", "Lindqvist", 1, [
        t.event("Birth", gdate(1868, 3, 14), vimmerby, citations=(c_birth,)),
        t.event("Death", gdate(1941, 11, 2), center_city),
        t.event("Immigration", gdate(1889), ellis, "Arrived from Sweden"),
        t.event("Residence", gdate(1910, 4, 21), center_city, "Farmer, own farm", citations=(c_census,)),
    ], notes=[note_anders])
    maria = t.person("Maria", "Lindqvist", 0, [
        t.event("Birth", gdate(1872, 7, 7), vimmerby),
        t.event("Death", gdate(1955, 1, 19), center_city),
        t.event("Immigration", gdate(1891), ellis),
        t.event("Residence", gdate(1910, 4, 21), center_city, citations=(c_census,)),
    ], alt_names=[t.name("Maria", "Johansson")], name_type="Married Name")
    karl = t.person("Karl", "Lindqvist", 1, [
        t.event("Birth", gdate(1895, 2, 3), center_city),
        t.event("Death", gdate(1968, 8, 30), minneapolis),
    ])
    elsa = t.person("Elsa", "Peterson", 0, [
        t.event("Birth", gdate(1898, 9, 21), center_city),
        t.event("Death", gdate(1990, 4, 4), minneapolis),
    ], alt_names=[t.name("Elsa", "Lindqvist")], name_type="Married Name")
    oskar = t.person("Oskar", "Lindqvist", 1, [
        t.event("Birth", gdate(1902, 3, 14), center_city),
        t.event("Death", gdate(1979), minneapolis),
    ])
    john = t.person("John", "Peterson", 1, [
        t.event("Birth", gdate(1894, modifier=ABOUT), minnesota),
        t.event("Death", gdate(1962), minneapolis),
    ])
    ruth = t.person("Ruth", "Peterson", 0, [
        t.event("Birth", gdate(1925, 6, 12), minneapolis),
        t.event("Death", gdate(2011)),
    ])
    harold = t.person("Harold", "Peterson", 1, [
        t.event("Birth", gdate(1928, 10, 2), minneapolis),
        t.event("Death", gdate(2001)),
    ])
    t.family(anders, maria, [karl, elsa, oskar], t.event("Marriage", gdate(1894, 5, 20), center_city))
    t.family(john, elsa, [ruth, harold], t.event("Marriage", gdate(1923, 6), minneapolis))
    return t


class Gramps:
    def __init__(self, base: str, user: str, password: str) -> None:
        self.api = base.rstrip("/") + "/api"
        self.user, self.password = user, password
        self.http = httpx.Client(timeout=120)
        self.token: str | None = None

    def ping(self) -> bool:
        return self.http.get(f"{self.api}/metadata/").status_code in (200, 401)

    def ensure_owner(self) -> None:
        r = self.http.post(f"{self.api}/token/create_owner/", json={})
        if r.status_code == 405:
            log("gramps: owner user already exists")
            return
        if r.status_code not in (200, 201):
            die(f"gramps create_owner token: {r.status_code} {r.text[:200]}")
        time.sleep(1.2)
        r = self.http.post(f"{self.api}/users/{self.user}/create_owner/",
                           headers={"Authorization": f"Bearer {r.json()['access_token']}"},
                           json={"password": self.password, "email": "owner@bifrost.dev",
                                 "full_name": "Dev Owner"})
        if r.status_code not in (200, 201):
            die(f"gramps create owner user: {r.status_code} {r.text[:200]}")
        log(f"gramps: created owner user '{self.user}'")

    def login(self) -> None:
        for _ in range(6):
            r = self.http.post(f"{self.api}/token/", json={"username": self.user, "password": self.password})
            if r.status_code != 429:
                break
            time.sleep(2)
        if r.status_code != 200:
            die(f"gramps login: {r.status_code} {r.text[:200]}")
        self.token = r.json()["access_token"]

    def _req(self, method: str, path: str, _retry: bool = True, ok_404: bool = False,
             **kw) -> httpx.Response:
        if not self.token:
            self.login()
        headers = dict(kw.pop("headers", None) or {})
        headers["Authorization"] = f"Bearer {self.token}"
        r = self.http.request(method, f"{self.api}{path}", headers=headers, **kw)
        if r.status_code == 401 and _retry:
            self.token = None
            return self._req(method, path, _retry=False, ok_404=ok_404, headers=headers, **kw)
        if r.status_code == 404 and ok_404:
            return r
        if r.status_code >= 400:
            die(f"gramps {method} {path}: {r.status_code} {r.text[:300]}")
        return r

    def get(self, path: str, **params):
        return self._req("GET", path, params=params).json()

    def find(self, path: str, **params) -> list:
        """List endpoints answer 404, not [], when a gramps_id filter matches nothing"""
        r = self._req("GET", path, ok_404=True, params=params)
        return [] if r.status_code == 404 else r.json()

    def count(self, path: str) -> int:
        r = self._req("GET", path, params={"pagesize": 1, "page": 1})
        return int(r.headers.get("X-Total-Count", 0))

    def create_objects(self, objs: list[dict]) -> None:
        self._req("POST", "/objects/", json=objs)

    def tag_handle(self, name: str) -> str | None:
        for t in self.get("/tags/", keys="handle,name"):
            if t.get("name") == name:
                return t["handle"]
        return None

    def import_file(self, path: Path, timeout: int = 1800) -> None:
        r = self._req("POST", "/importers/gramps/file", content=path.read_bytes(),
                      headers={"Content-Type": "application/octet-stream"})
        if r.status_code == 201:
            return
        task_id = ((r.json() or {}).get("task") or {}).get("id")
        if not task_id:
            die(f"gramps import: unexpected response {r.status_code} {r.text[:200]}")
        t0 = time.time()
        while time.time() - t0 < timeout:
            info = self.get(f"/tasks/{task_id}")
            state = info.get("state") or info.get("status") or ""
            if state == "SUCCESS":
                return
            if state in ("FAILURE", "REVOKED"):
                die(f"gramps import failed: {info}")
            time.sleep(5)
        die("gramps import did not finish in time")


def seed_gramps(args) -> dict:
    g = Gramps(URLS["gramps"], GRAMPS_USER, PASSWORD)
    wait_for("Gramps Web", g.ping)
    g.ensure_owner()
    g.login()
    meta = g.get("/metadata/")
    log(f"gramps: tree '{(meta.get('database') or {}).get('name')}', "
        f"web API v{(meta.get('gramps_webapi') or {}).get('version')}")

    place_tag = g.tag_handle(PLACE_TAG)
    if place_tag is None:
        tags = [{"_class": "Tag", "handle": handle(), "name": PLACE_TAG, "color": "#4a5bae",
                 "priority": 0, "change": NOW},
                {"_class": "Tag", "handle": handle(), "name": SKIP_TITLE_TAG, "color": "#b06a3b",
                 "priority": 1, "change": NOW}]
        g.create_objects(tags)
        place_tag = g.tag_handle(PLACE_TAG)
        log(f"gramps: created tags '{PLACE_TAG}' and '{SKIP_TITLE_TAG}'")

    if g.find("/people/", gramps_id="I9001"):
        log("gramps: sample tree already present")
    else:
        tree = build_tree(place_tag)
        g.create_objects(tree.objects)
        log(f"gramps: created sample tree ({len(tree.objects)} objects: Lindqvist and Peterson families)")

    if args.example_tree:
        example = DEV / "samples" / "example.gramps"
        if not example.exists():
            die(f"{example} missing (bifrost-dev.sh seed copies it out of the grampsweb container)")
        if g.count("/people/") > 500:
            log("gramps: example tree already imported")
        else:
            log("gramps: importing example.gramps (a couple of minutes)...")
            g.import_file(example)
            log(f"gramps: example tree imported, {g.count('/people/')} people now")
    return {"place_tag_handle": place_tag}


# ---------------------------------------------------------------- Paperless

class Paperless:
    def __init__(self, base: str, user: str, password: str) -> None:
        self.base = base.rstrip("/")
        self.user, self.password = user, password
        self.http = httpx.Client(timeout=120, headers={"Accept": "application/json; version=9"})
        self.token = ""

    def ping(self) -> bool:
        return self.http.get(f"{self.base}/api/").status_code < 500

    def login(self) -> None:
        r = self.http.post(f"{self.base}/api/token/", json={"username": self.user, "password": self.password})
        if r.status_code != 200:
            die(f"paperless token: {r.status_code} {r.text[:200]}")
        self.token = r.json()["token"]
        self.http.headers["Authorization"] = f"Token {self.token}"

    def _req(self, method: str, path: str, **kw) -> httpx.Response:
        r = self.http.request(method, f"{self.base}{path}", **kw)
        if r.status_code >= 400:
            die(f"paperless {method} {path}: {r.status_code} {r.text[:300]}")
        return r

    def get_or_create_tag(self, name: str) -> int:
        results = self._req("GET", "/api/tags/", params={"name__iexact": name}).json()["results"]
        if results:
            return results[0]["id"]
        r = self._req("POST", "/api/tags/", json={"name": name, "matching_algorithm": 0})
        log(f"paperless: created tag '{name}'")
        return r.json()["id"]

    def get_or_create_field(self, name: str, data_type: str, options: list[str] | None = None) -> dict:
        for f in self._req("GET", "/api/custom_fields/", params={"page_size": 200}).json()["results"]:
            if f["name"].lower() == name.lower():
                return f
        body: dict = {"name": name, "data_type": data_type}
        if options:
            body["extra_data"] = {"select_options": [{"label": o} for o in options]}
        r = self._req("POST", "/api/custom_fields/", json=body)
        log(f"paperless: created custom field '{name}' ({data_type})")
        return r.json()

    def find_document(self, title: str) -> int | None:
        results = self._req("GET", "/api/documents/",
                            params={"title__iexact": title, "fields": "id,title"}).json()["results"]
        return results[0]["id"] if results else None

    def post_document(self, path: Path, title: str, created: str, tag_ids: list[int]) -> str:
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        with path.open("rb") as fh:
            data: dict = {"title": title, "created": f"{created}T12:00:00"}
            if tag_ids:
                data["tags"] = [str(t) for t in tag_ids]
            r = self._req("POST", "/api/documents/post_document/",
                          files={"document": (path.name, fh, mime)}, data=data)
        return str(r.json()).strip('"')

    def wait_task(self, task_id: str, timeout: int = 900) -> int:
        t0 = time.time()
        while time.time() - t0 < timeout:
            rows = self._req("GET", "/api/tasks/", params={"task_id": task_id}).json()
            row = (rows[0] if isinstance(rows, list) and rows
                   else (rows.get("results") or [None])[0] if isinstance(rows, dict) else None)
            if row and row.get("status") == "SUCCESS":
                return int(row["related_document"])
            if row and row.get("status") == "FAILURE":
                die(f"paperless consumption failed: {row.get('result')}")
            time.sleep(3)
        die(f"paperless task {task_id} did not finish in {timeout}s")

    def patch(self, doc_id: int, body: dict) -> None:
        self._req("PATCH", f"/api/documents/{doc_id}/", json=body)


def seed_paperless(docs: list[dict]) -> dict:
    p = Paperless(URLS["paperless"], PAPERLESS_USER, PASSWORD)
    wait_for("Paperless-ngx", p.ping)
    p.login()
    log(f"paperless: authenticated as '{PAPERLESS_USER}'")
    tags = {name: p.get_or_create_tag(name) for name in PAPERLESS_TAGS}
    fields = {
        "Gramps ID": p.get_or_create_field("Gramps ID", "string"),
        "Gramps URL": p.get_or_create_field("Gramps URL", "url"),
        "Date qualifier": p.get_or_create_field("Date qualifier", "select", DATE_QUALIFIERS),
        "Source URL": p.get_or_create_field("Source URL", "url"),
    }
    qual_field = fields["Date qualifier"]
    qual_options = {o["label"]: o["id"] for o in qual_field.get("extra_data", {}).get("select_options", [])}
    missing = [q for q in DATE_QUALIFIERS if q not in qual_options]
    if missing:
        die(f"paperless: 'Date qualifier' field lacks options {missing}; fix it in Paperless")

    pending: list[tuple[str, dict]] = []
    for spec in docs:
        doc_id = p.find_document(spec["title"])
        if doc_id:
            spec["id"] = doc_id
            continue
        task = p.post_document(spec["path"], spec["title"], spec["created"],
                               [tags[t] for t in spec["tags"]])
        pending.append((task, spec))
        log(f"paperless: uploaded '{spec['title']}' ({spec['path'].name})")
    if pending:
        log(f"paperless: waiting for {len(pending)} document(s) to be consumed (OCR runs; ~30s each)...")
    for task, spec in pending:
        spec["id"] = p.wait_task(task)
        body: dict = {}
        if spec["qualifier"]:
            body["custom_fields"] = [{"field": qual_field["id"], "value": qual_options[spec["qualifier"]]}]
        if spec["content"]:
            body["content"] = spec["content"]
        if body:
            p.patch(spec["id"], body)
        log(f"paperless: #{spec['id']} '{spec['title']}' consumed"
            + (f", date qualifier {spec['qualifier']}" if spec["qualifier"] else "")
            + (", transcription text set" if spec["content"] else ""))
    return {"api_token": p.token, "tags": tags, "fields": {k: v["id"] for k, v in fields.items()}}


# ------------------------------------------------------------------- Immich

class Immich:
    def __init__(self, base: str) -> None:
        self.api = base.rstrip("/") + "/api"
        self.http = httpx.Client(timeout=300)

    def ping(self) -> bool:
        return self.http.get(f"{self.api}/server/ping").status_code == 200

    def _check(self, r: httpx.Response, what: str, ok=(200, 201, 204)) -> httpx.Response:
        if r.status_code not in ok:
            die(f"immich {what}: {r.status_code} {r.text[:300]}")
        return r

    def ensure_admin(self, email: str, name: str) -> None:
        r = self.http.post(f"{self.api}/auth/admin-sign-up",
                           json={"email": email, "name": name, "password": PASSWORD})
        if r.status_code == 201:
            log(f"immich: created admin {email}")
        elif r.status_code == 400:
            log("immich: admin already exists")
        else:
            self._check(r, "admin sign-up")

    def session(self, email: str) -> tuple[httpx.Client, str]:
        r = self._check(self.http.post(f"{self.api}/auth/login",
                                       json={"email": email, "password": PASSWORD}), f"login {email}")
        data = r.json()
        client = httpx.Client(base_url=self.api, timeout=300,
                              headers={"Authorization": f"Bearer {data['accessToken']}"})
        return client, data["userId"]

    def api_key(self, sess: httpx.Client, name: str = "bifrost-dev") -> str:
        for key in self._check(sess.get("/api-keys"), "list api keys").json():
            if key.get("name") == name:
                self._check(sess.delete(f"/api-keys/{key['id']}"), "delete api key")
        r = self._check(sess.post("/api-keys", json={"name": name, "permissions": ["all"]}), "create api key")
        return r.json()["secret"]

    def key_client(self, key: str) -> httpx.Client:
        return httpx.Client(base_url=self.api, timeout=300, headers={"x-api-key": key})

    def ensure_user(self, admin: httpx.Client, email: str, name: str) -> str:
        r = admin.post("/admin/users", json={"email": email, "name": name, "password": PASSWORD,
                                             "isAdmin": False, "shouldChangePassword": False})
        if r.status_code == 201:
            log(f"immich: created user {email}")
            return r.json()["id"]
        for u in self._check(admin.get("/admin/users"), "list users").json():
            if u["email"] == email:
                return u["id"]
        die(f"immich: could not create or find user {email}: {r.status_code} {r.text[:200]}")

    def ensure_partner(self, sess: httpx.Client, shared_with: str) -> None:
        r = sess.post("/partners", json={"sharedWithId": shared_with})
        if r.status_code not in (200, 201, 400):
            self._check(r, "partner sharing")

    def mark_onboarded(self, admin: httpx.Client, users: list[httpx.Client]) -> None:
        admin.post("/system-metadata/admin-onboarding", json={"isOnboarded": True})
        for u in users:
            u.put("/users/me/onboarding", json={"isOnboarded": True})

    def storage_template_enabled(self, admin: httpx.Client) -> bool:
        return bool((self._check(admin.get("/system-config"), "system config").json()
                     .get("storageTemplate") or {}).get("enabled"))

    def upsert_tags(self, client: httpx.Client, values: list[str]) -> dict[str, str]:
        self._check(client.put("/tags", json={"tags": values}), "upsert tags")
        return {t["value"].lower(): t["id"] for t in self._check(client.get("/tags"), "list tags").json()}

    def find_asset(self, client: httpx.Client, filename: str) -> dict | None:
        """Sample asset by file name; restores a trashed one"""
        r = self._check(client.post("/search/metadata",
                                    json={"originalFileName": filename, "size": 50, "page": 1,
                                          "withDeleted": True}), "search")
        for item in (r.json().get("assets") or {}).get("items") or []:
            if item.get("originalFileName") == filename:
                if item.get("isTrashed"):
                    self._check(client.post("/trash/restore/assets", json={"ids": [item["id"]]}),
                                "restore from trash")
                    log(f"immich: restored {filename} from the trash")
                return item
        return None

    def upload(self, client: httpx.Client, path: Path, when: dt.datetime) -> str:
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        stamp = when.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        fields = {"fileCreatedAt": stamp, "fileModifiedAt": stamp}
        for attempt in (fields, {**fields, "deviceAssetId": f"bifrost-dev-{path.name}", "deviceId": "bifrost-dev"}):
            with path.open("rb") as fh:
                r = client.post("/assets", files={"assetData": (path.name, fh, mime)}, data=attempt)
            if r.status_code in (200, 201):
                return r.json()["id"]
        die(f"immich upload {path.name}: {r.status_code} {r.text[:300]}")

    def tag_assets(self, client: httpx.Client, tag_id: str, asset_ids: list[str]) -> None:
        self._check(client.put(f"/tags/{tag_id}/assets", json={"ids": asset_ids}), "tag assets")

    def ensure_stack(self, client: httpx.Client, primary: str, others: list[str]) -> None:
        if self._check(client.get("/stacks", params={"primaryAssetId": primary}), "list stacks").json():
            return
        r = client.post("/stacks", json={"assetIds": [primary] + others})
        if r.status_code not in (200, 201):
            log(f"immich: stack not created ({r.status_code} {r.text[:120]})")

    def asset(self, client: httpx.Client, asset_id: str) -> dict:
        return self._check(client.get(f"/assets/{asset_id}"), "get asset").json()

    def ensure_person(self, client: httpx.Client, name: str) -> str:
        page = 1
        while True:
            data = self._check(client.get("/people", params={"page": page, "size": 500,
                                                             "withHidden": "true"}), "list people").json()
            for p in data.get("people") or []:
                if (p.get("name") or "").strip() == name:
                    return p["id"]
            if not data.get("hasNextPage"):
                break
            page += 1
        r = self._check(client.post("/people", json={"name": name}), "create person")
        log(f"immich: created person '{name}'")
        return r.json()["id"]

    def ensure_face(self, client: httpx.Client, asset_id: str, person_id: str,
                    box: tuple[float, float, float, float]) -> None:
        """Manually tagged face; box is (x, y, w, h) as fractions"""
        for f in self._check(client.get("/faces", params={"id": asset_id}), "list faces").json():
            if (f.get("person") or {}).get("id") == person_id:
                return
        a = self.asset(client, asset_id)
        exif = a.get("exifInfo") or {}
        w, h = exif.get("exifImageWidth") or a.get("width"), exif.get("exifImageHeight") or a.get("height")
        if not w or not h:
            log(f"immich: no dimensions yet for {asset_id}, face skipped (re-run the seed later)")
            return
        x, y, bw, bh = box
        self._check(client.post("/faces", json={
            "assetId": asset_id, "personId": person_id, "imageWidth": w, "imageHeight": h,
            "x": int(x * w), "y": int(y * h), "width": int(bw * w), "height": int(bh * h)}),
            "create face")


def exif_when(spec: dict) -> dt.datetime:
    return dt.datetime.strptime(spec["when"], "%Y:%m:%d %H:%M:%S")


def seed_immich(photos: list[dict], photos_dir: Path) -> dict:
    im = Immich(URLS["immich"])
    wait_for("Immich", im.ping)
    im.ensure_admin(*IMMICH_OWNER)
    owner_sess, owner_id = im.session(IMMICH_OWNER[0])
    partner_id = im.ensure_user(owner_sess, *IMMICH_PARTNER)
    partner_sess, _ = im.session(IMMICH_PARTNER[0])
    im.mark_onboarded(owner_sess, [owner_sess, partner_sess])
    im.ensure_partner(owner_sess, partner_id)
    im.ensure_partner(partner_sess, owner_id)
    log("immich: owner and partner share their libraries with each other")
    if im.storage_template_enabled(owner_sess):
        log("immich: WARNING storage template is enabled; originals then live under library/, "
            "so adjust the grampsweb mount and path mapping")
    keys = {"owner": im.api_key(owner_sess), "partner": im.api_key(partner_sess)}
    clients = {label: im.key_client(k) for label, k in keys.items()}
    log("immich: API keys 'bifrost-dev' (re)created for both accounts")
    tags = {label: im.upsert_tags(c, IMMICH_TAGS) for label, c in clients.items()}

    uploaded: dict[str, str] = {}
    first_owner_asset = None
    for spec in photos:
        client = clients[spec["account"]]
        existing = im.find_asset(client, spec["name"])
        if existing:
            asset_id = existing["id"]
        else:
            asset_id = im.upload(client, spec["path"], exif_when(spec))
            log(f"immich: uploaded {spec['name']} ({spec['account']})")
        uploaded[spec["name"]] = asset_id
        if spec["account"] == "owner" and first_owner_asset is None:
            first_owner_asset = asset_id
        for value in spec["tags"]:
            im.tag_assets(client, tags[spec["account"]][value.lower()], [asset_id])
    for spec in photos:
        if spec.get("stack_under"):
            im.ensure_stack(clients[spec["account"]], uploaded[spec["stack_under"]], [uploaded[spec["name"]]])
            log(f"immich: {spec['name']} stacked under {spec['stack_under']}")

    real = sorted(p for p in photos_dir.iterdir() if p.suffix.lower() in PHOTO_SUFFIXES) if photos_dir.is_dir() else []
    for path in real:
        client = clients["owner"]
        m = re.match(r"^(1[6-9]\d\d|20\d\d)\b", path.name)
        when = dt.datetime(int(m.group(1)), 1, 1, 12, 0, 0) if m else dt.datetime(2000, 1, 1, 12)
        existing = im.find_asset(client, path.name)
        asset_id = existing["id"] if existing else im.upload(client, path, when)
        if not existing:
            log(f"immich: uploaded {path.name} (owner)")
        values = ["Sync/Gramps"] + (["Sync/Date", "Date/Year"] if m else [])
        for value in values:
            im.tag_assets(client, tags["owner"][value.lower()], [asset_id])
        if first_owner_asset is None:
            first_owner_asset = asset_id
    if real:
        log(f"immich: {len(real)} photo(s) from {photos_dir} uploaded; face detection runs in the background "
            "(the ML container downloads its models on first use)")
    else:
        log(f"immich: no real photos in {photos_dir}; run 'bifrost-dev.sh fetch-photos' for faces")

    people = {}
    for account, name, spots in (
            ("owner", "Anders Lindqvist", [("wedding-1894.jpg", (0.28, 0.24, 0.20, 0.17)),
                                           ("lindqvist-farm-1923.jpg", (0.41, 0.38, 0.09, 0.14))]),
            ("owner", "Maria Lindqvist", [("wedding-1894.jpg", (0.55, 0.27, 0.19, 0.16))]),
            ("partner", "Elsa Peterson", [("elsa-about-1920.jpg", (0.36, 0.22, 0.28, 0.22))])):
        pid = im.ensure_person(clients[account], name)
        people[name] = (account, pid)
        for filename, box in spots:
            if filename in uploaded:
                im.ensure_face(clients[account], uploaded[filename], pid, box)
    log("immich: people Anders, Maria (owner) and Elsa (partner) with manually tagged faces")
    link_people(people, {"owner": owner_id, "partner": partner_id})

    prefix = "/data/upload/"
    if first_owner_asset:
        original = im.asset(clients["owner"], first_owner_asset).get("originalPath", "")
        marker = f"/{owner_id}/"
        if marker in original:
            prefix = original[: original.index(marker) + 1]
        else:
            log(f"immich: WARNING could not derive the upload prefix from originalPath {original!r}")
        log(f"immich: originals live under {prefix} (mounted into Gramps at /app/media/immich)")
    return {"keys": keys, "immich_prefix": prefix}


def link_people(people: dict[str, tuple[str, str]], user_ids: dict[str, str]) -> None:
    """Link Immich people to Gramps persons"""
    from bifrost.core import db
    from bifrost.modules import faces
    gramps_ids = {"Anders Lindqvist": "I9001", "Maria Lindqvist": "I9002", "Elsa Peterson": "I9004"}
    g = Gramps(URLS["gramps"], GRAMPS_USER, PASSWORD)
    conn = db.connect(DEV / "data" / "bifrost" / "bifrost.db")
    try:
        for name, (account, person_id) in people.items():
            found = g.find("/people/", gramps_id=gramps_ids[name])
            if not found:
                log(f"bifrost: no Gramps person {gramps_ids[name]} for {name}; link skipped")
                continue
            faces.set_link(conn, found[0]["handle"], person_id, "",
                           owner_user_id=user_ids[account])
    finally:
        conn.close()
    log(f"bifrost: {len(people)} Immich people linked to Gramps persons (Faces section)")


# ------------------------------------------------------------------- config

def write_config(gramps: dict, paperless: dict | None, immich: dict | None) -> None:
    cfg: dict = {
        "gramps": {"base_url": f"{URLS['gramps']}/api", "username": GRAMPS_USER, "password": PASSWORD},
        "paperless": {"base_url": URLS["paperless"],
                      "api_token": paperless["api_token"] if paperless else "not-seeded-yet"},
        "database": "data/bifrost/bifrost.db",
        "sync": {
            "immich": {
                "enabled": bool(immich),
                "sync_tag": "Sync/Gramps",
                "place_tag_handle": gramps["place_tag_handle"],
                "id_tag_prefix": "ID",
                "public_url": PUBLIC["immich"],
                "path_mappings": [{"immich_prefix": immich["immich_prefix"] if immich else "/data/upload/",
                                   "gramps_prefix": "immich/"}],
            },
            "paperless": {
                "sync_tags": ["doc", "img"],
                "public_url": PUBLIC["paperless"],
                "gramps_public_url": PUBLIC["gramps"],
                "gramps_id_field_id": paperless["fields"]["Gramps ID"] if paperless else None,
                "gramps_url_field_id": paperless["fields"]["Gramps URL"] if paperless else None,
                "date_qualifier_field_id": paperless["fields"]["Date qualifier"] if paperless else None,
                "source_url_field_id": paperless["fields"]["Source URL"] if paperless else None,
                "transcription_tag_id": paperless["tags"]["transcription"] if paperless else None,
                "ocr_tag": "Gemini OCR",
            },
        },
        "citations": {},
        "anthropic": {"api_key": os.environ.get("ANTHROPIC_API_KEY") or "REPLACE_ME",
                      "model": os.environ.get("ANTHROPIC_MODEL") or "claude-opus-4-8"},
        "gemini": {"api_key": os.environ.get("GEMINI_API_KEY") or "REPLACE_ME",
                   "model": os.environ.get("GEMINI_MODEL") or "gemini-3-flash-preview"},
        "places": {"boundaries_dir": "/boundaries"},
    }
    if immich:
        cfg["immich"] = {"base_url": URLS["immich"],
                         "accounts": [{"api_key": immich["keys"]["owner"], "label": "owner"},
                                      {"api_key": immich["keys"]["partner"], "label": "partner"}]}
    header = ("# Bifrost dev config, written by dev/seed/seed.py. Re-running the seed rewrites it.\n"
              "# Service URLs are the compose-network names; public_url values are what your browser uses.\n")
    CONFIG_OUT.write_text(header + yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
    log(f"wrote {CONFIG_OUT}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--example-tree", action="store_true", help="also import Gramps' example.gramps")
    ap.add_argument("--no-immich", action="store_true")
    ap.add_argument("--no-paperless", action="store_true")
    ap.add_argument("--photos-dir", type=Path, default=DEV / "samples" / "photos",
                    help="real photos to upload to Immich (default dev/samples/photos)")
    args = ap.parse_args()

    log(f"rendering sample documents and photos into {GENERATED}")
    generated = samples.generate(GENERATED)

    gramps = seed_gramps(args)
    paperless = None if args.no_paperless else seed_paperless(generated["documents"])
    immich = None if args.no_immich else seed_immich(generated["photos"], args.photos_dir)
    write_config(gramps, paperless, immich)

    print(f"""
[seed] done. Logins (password '{PASSWORD}' everywhere):
    Gramps Web  {PUBLIC['gramps']}     owner
    Paperless   {PUBLIC['paperless']}  admin
    Immich      {PUBLIC['immich']}     owner@bifrost.dev / partner@bifrost.dev
[seed] Bifrost picks up dev/config.yaml on its next start (bifrost-dev.sh seed restarts it).
[seed] In Bifrost, open Config to see all services green, then Sync -> Paperless / Immich preview.
""")


if __name__ == "__main__":
    main()
