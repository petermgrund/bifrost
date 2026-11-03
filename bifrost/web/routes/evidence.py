"""Evidence section API: claims, proofs and audits over the citations in Gramps, read-only"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from ...modules import evidence

router = APIRouter(prefix="/evidence", tags=["evidence"])
log = logging.getLogger("bifrost.evidence")

# the whole tree is read in about a second; keep it this long between requests
TTL_SECONDS = 30


def _state(request: Request):
    return request.app.state


def _public_url(cfg) -> str:
    return cfg.sync_paperless.gramps_public_url or cfg.sync_immich.gramps_public_url


def _require(st) -> None:
    if not st.cfg.evidence.enabled:
        raise HTTPException(503, "The Evidence section is off (evidence.enabled)")


async def _tree(st, refresh: bool = False) -> evidence.Tree:
    cached = st.caches.get("evidence.tree")
    if cached is not None and not refresh and time.time() - cached.loaded_at < TTL_SECONDS:
        return cached
    try:
        tree = await evidence.load_tree(st.gramps)
    except Exception as exc:  # noqa: BLE001
        log.warning("evidence: Gramps could not be read: %s", exc)
        raise HTTPException(503, f"Gramps could not be read: {str(exc)[:200]}")
    st.caches["evidence.tree"] = tree
    return tree


@router.get("")
async def evidence_page(request: Request):
    return RedirectResponse(url="/#evidence")


@router.get("/api/config")
async def config(request: Request) -> dict:
    cfg = _state(request).cfg
    return {
        "enabled": cfg.evidence.enabled,
        "gramps_public_url": _public_url(cfg),
        "cited_for": list(cfg.evidence.cited_for),
        "claim_words": {etype: list(words) for etype, words in cfg.evidence.claim_words},
        "tags": dict(cfg.evidence.tags),
    }


@router.get("/api/people")
async def people(request: Request, refresh: bool = False) -> dict:
    st = _state(request)
    _require(st)
    tree = await _tree(st, refresh)
    return {"people": evidence.people(tree), "loaded_at": tree.loaded_at}


@router.get("/api/person/{gramps_id}")
async def person(request: Request, gramps_id: str, refresh: bool = False) -> dict:
    st = _state(request)
    _require(st)
    tree = await _tree(st, refresh)
    handle = tree.by_gramps_id.get("person", {}).get(gramps_id)
    summary = evidence.person_summary(tree, st.cfg.evidence, handle, _public_url(st.cfg)) if handle else None
    if summary is None:
        raise HTTPException(404, f"No person {gramps_id}")
    return summary


@router.get("/api/claim/{claim_id}")
async def claim(request: Request, claim_id: str, refresh: bool = False) -> dict:
    st = _state(request)
    _require(st)
    tree = await _tree(st, refresh)
    found = evidence.claim_by_id(tree, claim_id)
    if found is None:
        raise HTTPException(404, f"No claim {claim_id}")
    return evidence.proof(tree, st.cfg.evidence, found, _public_url(st.cfg))


@router.get("/api/audits")
async def audits(request: Request, refresh: bool = False) -> dict:
    st = _state(request)
    _require(st)
    tree = await _tree(st, refresh)
    return evidence.audits(tree, st.cfg.evidence, _public_url(st.cfg))
