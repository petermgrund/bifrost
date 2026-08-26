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


async def probe_services(gramps, paperless, immich_accounts) -> list[dict]:
    immich = list(immich_accounts or [])
    rows = await asyncio.gather(
        _gramps_row(gramps),
        _paperless_row(paperless),
        *(_immich_row(c) for c in immich),
    )
    out = list(rows)
    if not immich:
        out.append({"key": "immich", "name": "Immich", "ok": False,
                    "detail": "not configured"})
    return out
