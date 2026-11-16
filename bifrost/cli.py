"""Bifrost CLI"""

from __future__ import annotations

import argparse
import asyncio
import sys

from .core import health
from .core.clients import GeminiClient, GrampsClient, ImmichClient, PaperlessClient
from .core.config import Config, ConfigError, load_config


def _clients(cfg: Config) -> tuple[GrampsClient, PaperlessClient, list[ImmichClient]]:
    gramps = GrampsClient(cfg.gramps.base_url, cfg.gramps.username, cfg.gramps.password)
    paperless = (PaperlessClient(cfg.paperless.base_url, cfg.paperless.api_token)
                 if cfg.paperless.base_url else None)
    accounts = []
    if cfg.immich.base_url:
        for acct in cfg.immich.accounts:
            client = ImmichClient(cfg.immich.base_url, acct.api_key)
            client.label = acct.label
            accounts.append(client)
    return gramps, paperless, accounts


async def _close(gramps, paperless, accounts) -> None:
    await gramps.close()
    if paperless is not None:
        await paperless.close()
    for client in accounts:
        await client.close()


async def _doctor(cfg: Config) -> int:
    gramps, paperless, accounts = _clients(cfg)
    gemini = GeminiClient(cfg.gemini.api_key, cfg.gemini.model)
    try:
        rows = await health.probe_services(gramps, paperless, accounts, gemini, cfg.sync_paperless.ocr_tag)
    finally:
        await _close(gramps, paperless, accounts)
        await gemini.close()
    width = max(len(r["name"]) for r in rows)
    marks = {True: "ok  ", False: "FAIL", None: "--  "}
    for r in rows:
        print(f"  {r['name'].ljust(width)}  {marks[r['ok']]}  {r['detail']}")
    return 1 if any(r["ok"] is False for r in rows) else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bifrost")
    parser.add_argument("--config", help="path to config.yaml (default: $BIFROST_CONFIG or repo root)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="connectivity + auth check against all services")
    args = parser.parse_args(argv)

    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    if args.command == "doctor":
        return asyncio.run(_doctor(cfg))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
