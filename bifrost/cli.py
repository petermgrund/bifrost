"""Bifrost CLI"""

from __future__ import annotations

import argparse
import asyncio
import sqlite3
import sys

from .core import health
from .core.clients import GrampsClient, ImmichClient, PaperlessClient
from .core.config import Config, ConfigError, load_config
from .modules import codes


def _clients(cfg: Config) -> tuple[GrampsClient, PaperlessClient, list[ImmichClient]]:
    gramps = GrampsClient(cfg.gramps.base_url, cfg.gramps.username, cfg.gramps.password)
    paperless = PaperlessClient(cfg.paperless.base_url, cfg.paperless.api_token)
    accounts = []
    if cfg.immich.base_url:
        for acct in cfg.immich.accounts:
            client = ImmichClient(cfg.immich.base_url, acct.api_key)
            client.label = acct.label
            accounts.append(client)
    return gramps, paperless, accounts


async def _close(gramps, paperless, accounts) -> None:
    await gramps.close()
    await paperless.close()
    for client in accounts:
        await client.close()


async def _doctor(cfg: Config) -> int:
    gramps, paperless, accounts = _clients(cfg)
    try:
        rows = await health.probe_services(gramps, paperless, accounts)
    finally:
        await _close(gramps, paperless, accounts)
    width = max(len(r["name"]) for r in rows)
    for r in rows:
        print(f"  {r['name'].ljust(width)}  {'ok  ' if r['ok'] else 'FAIL'}  {r['detail']}")
    return 0 if all(r["ok"] for r in rows) else 1


async def _import_withdrawn(cfg: Config, db_path: str) -> int:
    """The withdrawn codes of an old Bifrost database into the Gramps note"""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT gramps_id, withdrawn_at, withdrawn_reason, superseded_by FROM minted_media "
        "WHERE withdrawn_at IS NOT NULL AND length(gramps_id) = 6 ORDER BY withdrawn_at").fetchall()
    conn.close()
    gramps, paperless, accounts = _clients(cfg)
    added = 0
    try:
        known = await codes.withdrawn(gramps)
        for r in rows:
            code = codes.normalize(r["gramps_id"])
            if code in known:
                continue
            reason = r["withdrawn_reason"] or "withdrawn"
            if r["superseded_by"]:
                reason += f"; superseded by {r['superseded_by']}"
            await codes.withdraw(gramps, code, reason, when=(r["withdrawn_at"] or "")[:10])
            added += 1
        note = await codes.withdrawn_note(gramps)
    finally:
        await _close(gramps, paperless, accounts)
    print(f"{added} code(s) added to the '{codes.NOTE_TYPE}' note, {len(rows) - added} already there")
    if note:
        print(note["text"]["string"])
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bifrost")
    parser.add_argument("--config", help="path to config.yaml (default: $BIFROST_CONFIG or repo root)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="connectivity + auth check against all services")
    imp = sub.add_parser("import-withdrawn", help="copy an old database's withdrawn codes into Gramps")
    imp.add_argument("database", help="path to the old bifrost.db")
    args = parser.parse_args(argv)

    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    if args.command == "doctor":
        return asyncio.run(_doctor(cfg))
    if args.command == "import-withdrawn":
        return asyncio.run(_import_withdrawn(cfg, args.database))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
