"""Bifrost web app — Phase 0 stub (real pages land in Phase 1 with faces)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from .. import __version__

app = FastAPI(title="Bifrost", version=__version__)


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok", "version": __version__}


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return f"""<!doctype html>
<html><head><title>Bifrost</title></head>
<body style="font-family: system-ui; max-width: 40rem; margin: 4rem auto; color: #ddd; background: #1a1d23;">
<h1 style="color: #f0b429;">Bifrost <small style="font-size:.5em;color:#888">v{__version__}</small></h1>
<p><em>The bridge between realms: one console for everything Gramps.</em></p>
<p>Phase 0 — foundation. The faces page arrives in Phase 1.</p>
</body></html>"""
