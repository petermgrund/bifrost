"""Citation style page"""

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

from ...modules.citations import HOUSE_STYLE_SKELETON, master_path

router = APIRouter(prefix="/style", tags=["style"])
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")

BACKUP_DIR = Path(__file__).resolve().parents[3] / "data" / "house-style-backups"
KEEP_BACKUPS = 30


def _match_owner(path: Path, ref: os.stat_result) -> None:
    """Match the master's owner so container-root-created files stay host-manageable"""
    try:
        os.chown(path, ref.st_uid, ref.st_gid)
    except OSError:
        pass


@router.get("", response_class=HTMLResponse)
async def style_page(request: Request):
    return templates.TemplateResponse(request, "style.html", {})


@router.get("/api/doc")
async def read_doc() -> dict:
    master = master_path()
    if not master.exists():
        return {"text": HOUSE_STYLE_SKELETON, "mtime": 0, "size": 0,
                "exists": False}
    try:
        text = master.read_text(encoding="utf-8")
    except OSError as e:
        raise HTTPException(500, f"cannot read {master.name}: {e}")
    st = master.stat()
    return {"text": text, "mtime": st.st_mtime, "size": st.st_size,
            "exists": True}


class SaveBody(BaseModel):
    text: str
    base_mtime: float


@router.post("/api/doc")
async def save_doc(body: SaveBody) -> dict:
    if not body.text.strip():
        raise HTTPException(400, "refusing to save an empty document")

    master = master_path()
    creating = not master.exists()
    st: os.stat_result | None = None
    current: str | None = None
    if creating:
        if body.base_mtime:
            raise HTTPException(
                409, "document was deleted on disk since it was loaded")
    else:
        if not body.base_mtime:
            raise HTTPException(
                409, "document was created on disk since the skeleton was "
                     "loaded")
        try:
            st = master.stat()
            current = master.read_text(encoding="utf-8")
        except OSError as e:
            raise HTTPException(500, f"cannot read {master.name}: {e}")
        if abs(st.st_mtime - body.base_mtime) > 1e-6:
            raise HTTPException(
                409, "document changed on disk since it was loaded")

    text = body.text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.endswith("\n"):
        text += "\n"
    if not creating and text == current:
        return {"mtime": st.st_mtime, "size": st.st_size, "backup": None,
                "unchanged": True, "created": False}

    backup = None
    if creating:
        master.parent.mkdir(parents=True, exist_ok=True)
    else:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        _match_owner(BACKUP_DIR, st)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S.%f")
        backup = BACKUP_DIR / f"house_style_master.{stamp}.md"
        copy2(master, backup)
        _match_owner(backup, st)
        for old in sorted(BACKUP_DIR.glob("house_style_master.*.md"))[:-KEEP_BACKUPS]:
            old.unlink(missing_ok=True)

    tmp = master.with_name(master.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    if st is not None:
        os.chmod(tmp, stat_mod.S_IMODE(st.st_mode))
        _match_owner(tmp, st)
    os.replace(tmp, master)

    new = master.stat()
    return {"mtime": new.st_mtime, "size": new.st_size,
            "backup": backup.name if backup else None,
            "unchanged": False, "created": creating}
