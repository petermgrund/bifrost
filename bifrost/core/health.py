"""Service reachability"""

from __future__ import annotations

import asyncio


async def _gramps_row(gramps) -> dict:
    try:
        meta = await gramps.get_metadata()
    except Exception as exc:  # noqa: BLE001
        return {"key": "gramps", "name": "Gramps Web", "ok": False,
                "detail": str(exc)[:200]}
    version = (meta.get("gramps_webapi") or {}).get("version") or "?"
    return {"key": "gramps", "name": "Gramps Web", "ok": True,
            "detail": f"v{version}"}


async def _paperless_row(paperless) -> dict:
    try:
        version = await paperless.version()
    except Exception as exc:  # noqa: BLE001
        return {"key": "paperless", "name": "Paperless-ngx", "ok": False,
                "detail": str(exc)[:200]}
    return {"key": "paperless", "name": "Paperless-ngx", "ok": True,
            "detail": f"v{version or '?'}"}


async def _immich_row(client) -> dict:
    label = getattr(client, "label", "") or "account"
    row = {"key": f"immich:{label}", "name": f"Immich ({label})"}
    try:
        # may not need auth
        await client.get_me()
        version = await client.server_version()
    except Exception as exc:  # noqa: BLE001
        return {**row, "ok": False, "detail": str(exc)[:200]}
    return {**row, "ok": True, "detail": f"v{version or '?'}"}


async def _gemini_row(gemini, ocr_tag: str) -> dict:
    """ok is None when no key is set and nothing asks for one"""
    row = {"key": "gemini", "name": "Gemini"}
    if not gemini.configured:
        if ocr_tag:
            return {**row, "ok": False, "detail": f"No API key, but documents tagged '{ocr_tag}' need one"}
        return {**row, "ok": None, "detail": "No API key"}
    try:
        await gemini.check()
    except Exception as exc:  # noqa: BLE001
        return {**row, "ok": False, "detail": str(exc)[:200]}
    return {**row, "ok": True, "detail": gemini.model}


async def probe_services(gramps, paperless, immich_accounts, gemini=None, ocr_tag: str = "") -> list[dict]:
    immich = list(immich_accounts or [])
    rows = await asyncio.gather(
        _gramps_row(gramps),
        *([_paperless_row(paperless)] if paperless is not None else []),
        *(_immich_row(c) for c in immich),
        *([_gemini_row(gemini, ocr_tag)] if gemini is not None else []),
    )
    return list(rows)
