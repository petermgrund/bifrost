"""Inbox: records captured during research, filed in Paperless and Gramps until a citation shows them"""

from __future__ import annotations

import io
import json
import re
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import pypdfium2 as pdfium
from PIL import Image
from pypdf import PdfReader

from ..core.clients import PaperlessClient
from ..core.config import SyncPaperlessConfig

DETAIL_KEYS = ("platform", "collection", "reference", "page", "image", "images")
OPEN = ("processing", "filed", "transcribing")
PLATFORMS = (
    ("familysearch.org", "FamilySearch"),
    ("ancestry.", "Ancestry"),
    ("arkivdigital.", "ArkivDigital"),
    ("digitalarkivet.no", "Digitalarkivet"),
    ("riksarkivet.se", "Riksarkivet"),
    ("newspapers.com", "Newspapers.com"),
    ("findagrave.com", "Find a Grave"),
    ("myheritage.", "MyHeritage"),
    ("fold3.com", "Fold3"),
    ("genealogybank.com", "GenealogyBank"),
    ("chroniclingamerica.loc.gov", "Chronicling America"),
)
URL = re.compile(r"https?://[^\s<>\"']+")
REFERENCES = (
    ("DGS", re.compile(r"(?:image\s+group\s+number|\bDGS\b)[^0-9]{0,30}?(\d{6,9})", re.I)),
    ("Film", re.compile(r"\bfilm\s*(?:#|no\.|number)\s*:?\s*(\d{6,9})", re.I)),
    ("AID", re.compile(r"\bAID\s*:?\s*(v\d+(?:\.b\d+)?(?:\.s\d+)?)", re.I)),
    ("NAD", re.compile(r"\bNAD\s*:?\s*(SE/[^\s,;)]+)", re.I)),
    ("bildid", re.compile(r"\bbildid\s*[:=]?\s*([A-Z]?\d+_\d+)", re.I)),
    ("Roll", re.compile(r"\broll\s*(?:#|no\.)?\s*:?\s*([A-Z]?\d+(?:_\d+)?)\b", re.I)),
)
IMAGE = re.compile(r"(?<![\w.])(?:image|img|bild|bilde)\.?(?:\s+no\.)?\s*(\d{1,5})(?:\s*(?:of|av|/)\s*(\d{1,5}))?\b",
                   re.I)
PAGE = re.compile(r"(?<![\w.])(?:page|pp?\.|sid(?:a|an)?|s\.|side|folio|fol\.|sheet)(?:\s+(?:number|no\.))?\s*:?\s*"
                  r"(\d{1,5}[A-Za-z]?(?:\s*[–-]\s*\d{1,5}[A-Za-z]?)?)(?!\w)", re.I)
DATABASE = re.compile(r"^(?:.*?Ancestry\.com\.\s+)?(.+?)\s*\[database on-?line\]", re.I | re.M)
CRUMB = re.compile(r"\s*(?:›|»|→|->|>)\s*")
DUPLICATE = re.compile(r"duplicate.*?#\s*(\d+)", re.I | re.S)
IMAGE_MIMES = ("image/jpeg", "image/png", "image/tiff", "image/webp")
EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/tiff": "tif", "image/webp": "webp",
              "application/pdf": "pdf"}
MAX_FILE = 200 * 1024 * 1024


class CaptureError(Exception):
    """A refused capture, with the HTTP status that fits it"""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text(value) -> str:
    return " ".join(str(value or "").split())


def platform_of(url: str) -> str:
    """The platform a link points into, by its host"""
    host = (urlparse(url).hostname or "").lower()
    for key, name in PLATFORMS:
        if key in host:
            return name
    return host.removeprefix("www.")


def _aid(aid: str) -> dict:
    """The image (b) and page (s) an ArkivDigital AID names"""
    found = {}
    if m := re.search(r"\.b(\d+)", aid):
        found["image"] = m[1]
    if m := re.search(r"\.s(\d+)", aid):
        found["page"] = m[1]
    return found


def _from_url(url: str) -> dict:
    parts = urlparse(url)
    host = (parts.hostname or "").lower()
    found = {}
    if "familysearch.org" in host:
        if m := re.search(r"/film/(\d{6,9})", parts.path):
            found["reference"] = f"DGS {m[1]}"
        index = (parse_qs(parts.query).get("i") or [""])[0]
        if index.isdigit():
            found["image"] = str(int(index) + 1)
    elif "arkivdigital" in host and (m := re.search(r"v\d+(?:\.b\d+)?(?:\.s\d+)?", parts.path)):
        found = {"reference": f"AID {m[0]}", **_aid(m[0])}
    return found


def _carries(line: str) -> bool:
    return any(p.search(line) for _, p in REFERENCES) or bool(IMAGE.search(line) or PAGE.search(line))


def _strip(line: str) -> str:
    """The line without its links, references, pages and images"""
    out = URL.sub(" ", line)
    for _, pattern in REFERENCES:
        out = pattern.sub(" ", out)
    out = PAGE.sub(" ", IMAGE.sub(" ", out))
    out = re.sub(r"\(\s*[\s,;:/·]*\)", " ", out)
    out = re.sub(r"(?:\s*;\s*)+", "; ", _text(out))
    return out.strip(" -–—·|,;:/")


def _collection(text: str) -> str:
    if m := DATABASE.search(text):
        return _text(m[1]).strip(" .")
    crumbs, carriers, commas = [], [], []
    for raw in text.splitlines():
        line = _strip(raw)
        if not line or line.endswith(":") or not re.search(r"[^\W\d_]", line):
            continue
        if CRUMB.search(line):
            crumbs.append(line)
        elif _carries(raw):
            carriers.append(line)
        elif "," in line:
            commas.append(line)
    pick = (crumbs or carriers or commas or [""])[0]
    return " › ".join(part for part in CRUMB.split(pick) if part)


def read_paste(text: str) -> dict:
    """The link, platform, collection, reference, page and image a pasted clip names"""
    text = text or ""
    found: dict = {}
    refs: list[str] = []
    urls = [u.rstrip(".,;)") for u in URL.findall(text)]
    if urls:
        link = next((u for u in urls if "familysearch.org" in u), urls[0])
        from_link = _from_url(link)
        if ref := from_link.pop("reference", ""):
            refs.append(ref)
        found.update(link=link, platform=platform_of(link), **from_link)
    for label, pattern in REFERENCES:
        for m in pattern.finditer(text):
            if (ref := f"{label} {m[1]}") not in refs:
                refs.append(ref)
            if label == "AID":
                for key, value in _aid(m[1]).items():
                    found.setdefault(key, value)
    found["reference"] = " · ".join(refs)
    if m := IMAGE.search(text):
        found["image"], found["images"] = m[1], m[2] or ""
    if m := PAGE.search(text):
        found["page"] = m[1]
    found["collection"] = _collection(text)
    return {k: v for k, v in found.items() if v}


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower().replace(".com", ""))


def match_name(name: str, options: list[dict]) -> int | None:
    """The id of the option named like `name`, ignoring case, punctuation and '.com', else a prefix match"""
    want = _norm(name)
    if not want:
        return None
    named = [(o["id"], _norm(o.get("name") or "")) for o in options]
    exact = next((i for i, n in named if n == want), None)
    if exact is not None:
        return exact
    return next((i for i, n in named if n and (n.startswith(want) or want.startswith(n))), None)


def fallback_title(details: dict, file_name: str) -> str:
    """A capture's title when none is typed: the collection's last part and the page or image, else the file name"""
    last = (details.get("collection") or "").split(" › ")[-1].strip()
    spot = (f"page {details['page']}" if details.get("page")
            else f"image {details['image']}" if details.get("image") else "")
    title = ", ".join(p for p in (last, spot) if p) or file_name.rsplit(".", 1)[0]
    return title[:1].upper() + title[1:] if title else "Capture"


def where(details: dict) -> str:
    """Reference, page and image in one line: 'DGS 005537573, page 296, image 32 of 644'"""
    image = details.get("image") or ""
    if image and details.get("images"):
        image = f"{image} of {details['images']}"
    line = ", ".join(p for p in (details.get("reference") or "",
                                 f"page {details['page']}" if details.get("page") else "",
                                 f"image {image}" if image else "") if p)
    return line[:1].upper() + line[1:]


def paperless_note(note: str, link: str, details: dict) -> str:
    """The Paperless note a capture leaves: what was typed, then where the record is"""
    place = "\n".join(p for p in (details.get("collection") or "", where(details), link) if p)
    return "\n\n".join(p for p in ((note or "").strip(), place) if p)


def consume_error(result: str | None) -> str:
    """Why Paperless refused a capture"""
    text = _text(result)
    if m := DUPLICATE.search(text):
        return f"Already in Paperless as #{m[1]}"
    return text[:300] or "Paperless refused the file"


def sniff(data: bytes) -> str:
    """The file's type from its first bytes"""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] in (b"II*\x00", b"MM\x00*"):
        return "image/tiff"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:5] == b"%PDF-":
        return "application/pdf"
    return ""


def page_count(data: bytes, mime: str) -> int:
    if mime == "application/pdf":
        return len(PdfReader(io.BytesIO(data)).pages)
    with Image.open(io.BytesIO(data)) as im:
        return getattr(im, "n_frames", 1) or 1


class FileStore:
    """Files added on the capture card, held in memory until Save files them in Paperless"""

    def __init__(self, ttl: float = 6 * 3600) -> None:
        self.ttl = ttl
        self._files: dict[str, dict] = {}

    def add(self, name: str, data: bytes) -> dict:
        self._prune()
        mime = sniff(data)
        if not mime:
            raise CaptureError(415, f"{name or 'This file'} isn't a JPEG, PNG, TIFF, WebP or PDF")
        try:
            pages = page_count(data, mime)
        except Exception as exc:  # noqa BLE001
            raise CaptureError(415, f"{name or 'This file'} can't be read: {exc}") from exc
        name = (name or "").strip() or f"capture.{EXTENSIONS[mime]}"
        fid = uuid.uuid4().hex
        self._files[fid] = {"name": name, "data": data, "mime": mime, "pages": pages, "at": time.monotonic()}
        return {"file": fid, "name": name, "mime": mime, "pages": pages}

    def take(self, ids: list[str]) -> list[dict]:
        if any(i not in self._files for i in ids):
            raise CaptureError(410, "A file is no longer on the card. Add it again.")
        return [self._files[i] for i in ids]

    def drop(self, ids: list[str]) -> None:
        for i in ids:
            self._files.pop(i, None)

    def _prune(self) -> None:
        cutoff = time.monotonic() - self.ttl
        for fid in [f for f, v in self._files.items() if v["at"] < cutoff]:
            del self._files[fid]


def _as_jpeg(data: bytes, mime: str) -> tuple[bytes, tuple[int, int], float]:
    with Image.open(io.BytesIO(data)) as im:
        size = im.size
        dpi = float((im.info.get("dpi") or (0, 0))[0] or 0) or 150.0
        if mime == "image/jpeg" and im.mode in ("RGB", "L", "CMYK"):
            return data, size, dpi
        buf = io.BytesIO()
        im.convert("RGB").save(buf, "JPEG", quality=95)
        return buf.getvalue(), size, dpi


def build_upload(files: list[dict]) -> tuple[str, bytes, str, int]:
    """One file as it is, or several images as one PDF that keeps their JPEG data untouched"""
    if len(files) == 1:
        f = files[0]
        return f["name"], f["data"], f["mime"], f["pages"]
    if any(f["mime"] not in IMAGE_MIMES or f["pages"] != 1 for f in files):
        raise CaptureError(400, "Add one PDF, or several single-page images")
    pdf = pdfium.PdfDocument.new()
    buffers = []
    for f in files:
        jpeg, (w, h), dpi = _as_jpeg(f["data"], f["mime"])
        pw, ph = w * 72 / dpi, h * 72 / dpi
        page = pdf.new_page(pw, ph)
        image = pdfium.PdfImage.new(pdf)
        buffers.append(io.BytesIO(jpeg))
        image.load_jpeg(buffers[-1], inline=False)
        image.set_matrix(pdfium.PdfMatrix().scale(pw, ph))
        page.insert_obj(image)
        page.gen_content()
    out = io.BytesIO()
    pdf.save(out)
    stem = files[0]["name"].rsplit(".", 1)[0] or "capture"
    return f"{stem}.pdf", out.getvalue(), "application/pdf", len(files)


def insert_capture(conn: sqlite3.Connection, *, title: str, link: str, details: dict, note: str,
                   transcribe: bool, file_name: str, pages: int, task_id: str) -> int:
    stamp = now()
    with conn:
        cur = conn.execute(
            "INSERT INTO captures (title, link, details, note, transcribe, file_name, pages, task_id, state,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'processing', ?, ?)",
            (title, link, json.dumps(details, ensure_ascii=False), note, int(transcribe), file_name, pages,
             task_id, stamp, stamp))
    return cur.lastrowid


def get_capture(conn: sqlite3.Connection, cid: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM captures WHERE id=?", (cid,)).fetchone()


UPDATABLE = ("doc_id", "gramps_id", "state", "error", "cited_at", "removed_at")


def update_capture(conn: sqlite3.Connection, cid: int, **fields) -> None:
    cols = [c for c in UPDATABLE if c in fields]
    with conn:
        conn.execute(f"UPDATE captures SET {''.join(f'{c}=?, ' for c in cols)}updated_at=? WHERE id=?",
                     (*(fields[c] for c in cols), now(), cid))


def open_captures(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Captures neither cited nor removed, newest first"""
    return conn.execute("SELECT * FROM captures WHERE cited_at IS NULL AND removed_at IS NULL "
                        "ORDER BY id DESC").fetchall()


def captured_docs(conn: sqlite3.Connection) -> set[int]:
    return {r["doc_id"] for r in conn.execute("SELECT doc_id FROM captures WHERE doc_id IS NOT NULL")}


def remove_capture(conn: sqlite3.Connection, cid: int) -> bool:
    """Take a capture off the Inbox; one that never reached Paperless is forgotten"""
    row = get_capture(conn, cid)
    if row is None:
        return False
    if row["doc_id"] is None and row["state"] == "failed":
        with conn:
            conn.execute("DELETE FROM captures WHERE id=?", (cid,))
    else:
        update_capture(conn, cid, removed_at=now())
    return True


def hide_doc(conn: sqlite3.Connection, doc_id: int) -> None:
    with conn:
        conn.execute("INSERT OR REPLACE INTO inbox_hidden (doc_id, hidden_at) VALUES (?, ?)", (doc_id, now()))


def hidden_docs(conn: sqlite3.Connection) -> set[int]:
    return {r["doc_id"] for r in conn.execute("SELECT doc_id FROM inbox_hidden")}


def stale(row: sqlite3.Row, seconds: float) -> bool:
    """Whether the capture has gone `seconds` without a change"""
    try:
        changed = datetime.fromisoformat(row["updated_at"])
    except (TypeError, ValueError):
        return True
    return (datetime.now(timezone.utc) - changed).total_seconds() >= seconds


def details_of(row: sqlite3.Row) -> dict:
    try:
        return json.loads(row["details"] or "{}")
    except ValueError:
        return {}


def public(row: sqlite3.Row) -> dict:
    """A capture as the Inbox page lists it"""
    details = details_of(row)
    return {"key": f"capture:{row['id']}", "id": row["id"], "doc_id": row["doc_id"],
            "pid": row["gramps_id"] or "", "title": row["title"], "link": row["link"],
            "details": {k: details.get(k, "") for k in DETAIL_KEYS}, "pages": row["pages"],
            "state": row["state"], "error": row["error"] or "", "older": False}


def older_row(doc: dict, pid: str) -> dict:
    """An older synced document as the Inbox page lists it"""
    return {"key": f"doc:{doc['id']}", "id": None, "doc_id": doc["id"], "pid": pid,
            "title": doc.get("title") or f"#{doc['id']}", "link": "", "details": {}, "pages": None,
            "state": "synced", "error": "", "older": True}


async def capture(paperless: PaperlessClient, conn: sqlite3.Connection, cfg: SyncPaperlessConfig,
                  files: FileStore, ids: list[str], *, title: str, link: str, details: dict, note: str,
                  transcribe: bool, pasted: str = "") -> dict:
    """File the card's files in Paperless as one document with its title, platform, link and tags"""
    if not ids:
        raise CaptureError(400, "Add a file")
    if not cfg.sync_tags:
        raise CaptureError(400, "No sync tag is configured (sync.paperless.sync_tags)")
    name, data, mime, pages = build_upload(files.take(ids))
    if same := await paperless.documents_with_bytes(data):
        known = same[0].get("title")
        raise CaptureError(409, f"Already in Paperless as #{same[0]['id']}" + (f": {known}" if known else ""))
    link = _text(link)
    found = {k: _text(details.get(k)) for k in DETAIL_KEYS}
    found["platform"] = platform_of(link) if link else ""
    title = _text(title) or fallback_title(found, name)
    transcribe = bool(transcribe and cfg.ocr_tag)
    tags = []
    for tag in [cfg.sync_tags[0]] + ([cfg.ocr_tag] if transcribe else []):
        tag_id = await paperless.resolve_tag_id(tag)
        if tag_id is None:
            raise CaptureError(400, f"Paperless has no tag named {tag!r}")
        tags.append(tag_id)
    correspondent = match_name(found["platform"], await paperless.correspondents()) if found["platform"] else None
    fields = {cfg.source_url_field_id: link} if cfg.source_url_field_id and link else None
    task_id = await paperless.post_document(data, name, mime, title=title, tags=tags,
                                            correspondent=correspondent, custom_fields=fields)
    files.drop(ids)
    cid = insert_capture(conn, title=title, link=link, details={**found, "pasted": (pasted or "").strip()},
                         note=(note or "").strip(), transcribe=transcribe, file_name=name, pages=pages,
                         task_id=task_id)
    return public(get_capture(conn, cid))
