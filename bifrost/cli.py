"""Bifrost CLI"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from .core import db
from .core.clients import GrampsClient, ImmichClient, PaperlessClient
from .core.config import Config, ConfigError, load_config
from .core.events import SyncEvent
from .modules import photos_handover
from .modules.sync_immich import SyncError
from .web.runs import record_run


def _ok(label: str, detail: str) -> tuple[str, bool, str]:
    return (label, True, detail)


def _fail(label: str, exc: Exception) -> tuple[str, bool, str]:
    return (label, False, f"{type(exc).__name__}: {exc}")


async def _doctor(cfg: Config) -> int:
    checks: list[tuple[str, bool, str]] = []

    try:
        conn = db.connect(cfg.db_path)
        version = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()["v"]
        conn.close()
        checks.append(_ok("database", f"{cfg.db_path} (schema v{version})"))
    except Exception as exc:  # noqa: BLE001
        checks.append(_fail("database", exc))

    async def check_gramps() -> tuple[str, bool, str]:
        try:
            async with GrampsClient(cfg.gramps.base_url, cfg.gramps.username, cfg.gramps.password) as gc:
                meta = await gc.get_metadata()
            tree = (meta.get("database") or {}).get("name") or "?"
            version = (meta.get("gramps_webapi") or {}).get("version") or "?"
            return _ok("gramps", f"tree '{tree}', web API v{version}")
        except Exception as exc:  # noqa: BLE001
            return _fail("gramps", exc)

    async def check_paperless() -> tuple[str, bool, str]:
        try:
            async with PaperlessClient(cfg.paperless.base_url, cfg.paperless.api_token) as pc:
                n = await pc.count_tags()
            return _ok("paperless", f"authenticated, {n} tags")
        except Exception as exc:  # noqa: BLE001
            return _fail("paperless", exc)

    checks.extend(await asyncio.gather(check_gramps(), check_paperless()))

    width = max(len(label) for label, _, _ in checks)
    failed = False
    for label, ok, detail in checks:
        mark = "ok  " if ok else "FAIL"
        print(f"  {label.ljust(width)}  {mark}  {detail}")
        failed = failed or not ok
    return 1 if failed else 0


def _print_event(ev: SyncEvent) -> None:
    who = ev.gramps_id or ev.source_id or ""
    bits = [f"  {ev.entity or '':<6} {ev.action or '':<12} {who:<8}"]
    if ev.title:
        bits.append(ev.title[:60])
    if ev.detail:
        bits.append(ev.detail)
    if ev.data and ev.data.get("cols"):
        bits.append(", ".join(f"{k}: {v}" for k, v in ev.data["cols"].items()))
    print("  ".join(bits))


async def _printed(events):
    async for ev in events:
        if ev.kind == "item":
            _print_event(ev)
        yield ev


async def _handover(cfg: Config, args) -> int:
    accounts = []
    if cfg.immich.base_url:
        for acct in cfg.immich.accounts:
            client = ImmichClient(cfg.immich.base_url, acct.api_key)
            client.label = acct.label
            accounts.append(client)
    if not accounts:
        print("Immich is not configured (immich.base_url/accounts)", file=sys.stderr)
        return 2
    conn = db.connect(cfg.db_path)
    gramps = GrampsClient(cfg.gramps.base_url, cfg.gramps.username, cfg.gramps.password)
    if args.apply:
        job = "photos.handover.apply"
        gen = photos_handover.apply(gramps, accounts, conn, cfg.sync_immich, Path(args.apply))
    elif args.cleanup_tags:
        job = "photos.handover.cleanup"
        gen = photos_handover.cleanup_tags(accounts, conn, cfg.sync_immich)
    else:
        out = Path(args.out) if args.out else cfg.db_path.parent / "photos-handover.csv"
        job = "photos.handover.dry-run"
        gen = photos_handover.dry_run(gramps, accounts, conn, cfg.sync_immich, out)
    try:
        run_id, events = await record_run(conn, job, _printed(gen))
    except SyncError as exc:
        print(f"error: {exc.detail}", file=sys.stderr)
        return 1
    finally:
        await gramps.close()
        for client in accounts:
            await client.close()
        conn.close()
    summary = next((e for e in reversed(events) if e.kind == "summary"), None)
    data = (summary.data or {}) if summary else {}
    print(f"run {run_id}: {summary.detail if summary else job}")
    for key, value in data.items():
        print(f"  {key.replace('_', ' ')}: {value}")
    return 1 if data.get("blocked") or data.get("errors") else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bifrost")
    parser.add_argument("--config", help="path to config.yaml (default: $BIFROST_CONFIG or repo root)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="connectivity + auth check against all services")
    handover = sub.add_parser("photos-handover",
                              help="move photo facts from Immich and Bifrost's tables onto the Gramps media")
    mode = handover.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true",
                      help="write the decisions CSV and list what --apply would do (the default)")
    mode.add_argument("--apply", metavar="DECISIONS_CSV",
                      help="apply the keep=immich rows, then write Bifrost's notes and links to Gramps")
    mode.add_argument("--cleanup-tags", action="store_true",
                      help="remove the Date, Place and field-sync tags from photos in Gramps")
    handover.add_argument("--out", help="where --dry-run writes the CSV (default: next to the database)")
    args = parser.parse_args(argv)

    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    if args.command == "doctor":
        return asyncio.run(_doctor(cfg))
    if args.command == "photos-handover":
        return asyncio.run(_handover(cfg, args))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
