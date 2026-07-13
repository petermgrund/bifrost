"""House style — edit the house-style master document from the browser.

Reads and writes the same file the citation composer loads fresh on every
compose call (modules/citations.py), so a save takes effect immediately.
"""

from __future__ import annotations

import os
import stat as stat_mod
from datetime import datetime
from pathlib import Path
from shutil import copy2

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from ...modules.citations import MASTER_PATH as MASTER

router = APIRouter(prefix="/style", tags=["style"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")

BACKUP_DIR = Path(__file__).resolve().parents[3] / "data" / "house-style-backups"
KEEP_BACKUPS = 30


def _match_owner(path: Path, ref: os.stat_result) -> None:
    """Give container-root-created files the master's owner (peter on the
    host) so the working tree stays host-manageable. No-op where not root."""
    try:
        os.chown(path, ref.st_uid, ref.st_gid)
    except OSError:
        pass


@router.get("", response_class=HTMLResponse)
async def style_page(request: Request):
    return templates.TemplateResponse(request, "style.html", {})


@router.get("/api/doc")
async def read_doc() -> dict:
    try:
        text = MASTER.read_text(encoding="utf-8")
    except OSError as e:
        raise HTTPException(500, f"cannot read {MASTER.name}: {e}")
    st = MASTER.stat()
    return {"text": text, "mtime": st.st_mtime, "size": st.st_size}


class SaveBody(BaseModel):
    text: str
    base_mtime: float


@router.post("/api/doc")
async def save_doc(body: SaveBody) -> dict:
    if not body.text.strip():
        raise HTTPException(400, "refusing to save an empty document")

    try:
        st = MASTER.stat()
        current = MASTER.read_text(encoding="utf-8")
    except OSError as e:
        raise HTTPException(500, f"cannot read {MASTER.name}: {e}")
    # The doc is also edited outside Bifrost; refuse to clobber a version the
    # editor never saw. The client reloads and the user re-applies.
    if abs(st.st_mtime - body.base_mtime) > 1e-6:
        raise HTTPException(
            409, "document changed on disk since it was loaded — reload to pick "
                 "up the newer version")

    text = body.text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.endswith("\n"):
        text += "\n"
    if text == current:
        return {"mtime": st.st_mtime, "size": st.st_size, "backup": None,
                "unchanged": True}

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    _match_owner(BACKUP_DIR, st)
    # Microsecond stamp: two saves in the same second must not share a name —
    # copy2 would silently overwrite the earlier restore point.
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S.%f")
    backup = BACKUP_DIR / f"house_style_master.{stamp}.md"
    copy2(MASTER, backup)
    _match_owner(backup, st)
    for old in sorted(BACKUP_DIR.glob("house_style_master.*.md"))[:-KEEP_BACKUPS]:
        old.unlink(missing_ok=True)

    # Crash-safe atomic write: temp file in the same directory, then rename.
    # Safe against the bind mount because /app/repo is a DIRECTORY mount (a
    # rename inside it is just a rename on the host); the old single-file
    # mount would have been detached by this.
    tmp = MASTER.with_name(MASTER.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp, stat_mod.S_IMODE(st.st_mode))
    _match_owner(tmp, st)
    os.replace(tmp, MASTER)

    new = MASTER.stat()
    return {"mtime": new.st_mtime, "size": new.st_size, "backup": backup.name,
            "unchanged": False}
