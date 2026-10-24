"""Bifrost CLI"""

from __future__ import annotations

import argparse
import asyncio
import sys

from .core import db
from .core.clients import GrampsClient, ImmichClient, PaperlessClient
from .core.config import Config, ConfigError, load_config
from .core.events import SyncEvent
from .modules import reconcile
from .web.runs import record_run


def _ok(label: str, detail: str) -> tuple[str, bool, str]:
    return (label, True, detail)


def _fail(label: str, exc: Exception) -> tuple[str, bool, str]:
    return (label, False, f"{type(exc).__name__}: {exc}")


def _immich_accounts(cfg: Config) -> list[ImmichClient]:
    accounts = []
    if cfg.immich.base_url:
        for acct in cfg.immich.accounts:
            client = ImmichClient(cfg.immich.base_url, acct.api_key)
            client.label = acct.label
            accounts.append(client)
    return accounts


async def _doctor(cfg: Config) -> int:
    checks: list[tuple[str, bool, str]] = []

    try:
        conn = db.connect(cfg.db_path)
        version = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()["v"]
        checks.append(_ok("database", f"{cfg.db_path} (schema v{version})"))
    except Exception as exc:  # noqa: BLE001
        conn = None
        checks.append(_fail("database", exc))

    gramps = GrampsClient(cfg.gramps.base_url, cfg.gramps.username, cfg.gramps.password)
    paperless = PaperlessClient(cfg.paperless.base_url, cfg.paperless.api_token)
    accounts = _immich_accounts(cfg)

    async def check_gramps() -> tuple[str, bool, str]:
        try:
            meta = await gramps.get_metadata()
            tree = (meta.get("database") or {}).get("name") or "?"
            version = (meta.get("gramps_webapi") or {}).get("version") or "?"
            return _ok("gramps", f"tree '{tree}', web API v{version}")
        except Exception as exc:  # noqa: BLE001
            return _fail("gramps", exc)

    async def check_paperless() -> tuple[str, bool, str]:
        try:
            n = await paperless.count_tags()
            return _ok("paperless", f"authenticated, {n} tags")
        except Exception as exc:  # noqa: BLE001
            return _fail("paperless", exc)

    async def check_register() -> tuple[str, bool, str]:
        if conn is None:
            return _fail("register", RuntimeError("no database"))
        summary: dict = {}
        async for ev in reconcile.scan(gramps, paperless, accounts, conn):
            if ev.kind == "error":
                return _fail("register", RuntimeError(ev.detail))
            if ev.kind == "summary":
                summary = ev.data or {}
        pending = {k: v for k, v in summary.items() if v and k != "errors"}
        if not pending:
            return _ok("register", "agrees with Gramps")
        return (
            "register", False,
            ", ".join(f"{v} to {k.rstrip('ed')}" if k != "attention" else f"{v} needing attention"
                      for k, v in pending.items()) + " (run reconcile)")

    try:
        checks.extend(await asyncio.gather(check_gramps(), check_paperless()))
        checks.append(await check_register())
    finally:
        await gramps.close()
        await paperless.close()
        for client in accounts:
            await client.close()
        if conn is not None:
            conn.close()

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
        if ev.kind in ("item", "error"):
            _print_event(ev)
        yield ev


async def _reconcile(cfg: Config, apply: bool) -> int:
    conn = db.connect(cfg.db_path)
    gramps = GrampsClient(cfg.gramps.base_url, cfg.gramps.username, cfg.gramps.password)
    paperless = PaperlessClient(cfg.paperless.base_url, cfg.paperless.api_token)
    accounts = _immich_accounts(cfg)
    job = "codes.reconcile" if apply else "codes.reconcile.preview"
    try:
        run_id, events = await record_run(
            conn, job, _printed(reconcile.scan(gramps, paperless, accounts, conn, apply=apply)))
    finally:
        await gramps.close()
        await paperless.close()
        for client in accounts:
            await client.close()
        conn.close()
    summary = next((e for e in reversed(events) if e.kind == "summary"), None)
    data = (summary.data or {}) if summary else {}
    print(f"run {run_id}: {'applied' if apply else 'preview'}")
    for key, value in data.items():
        print(f"  {key}: {value}")
    return 1 if data.get("errors") else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bifrost")
    parser.add_argument("--config", help="path to config.yaml (default: $BIFROST_CONFIG or repo root)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="connectivity + auth check against all services, and the register")
    rec = sub.add_parser("reconcile", help="compare the register with Gramps, Immich and Paperless")
    rec.add_argument("--apply", action="store_true", help="repair the register (the default only reports)")
    args = parser.parse_args(argv)

    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    if args.command == "doctor":
        return asyncio.run(_doctor(cfg))
    if args.command == "reconcile":
        return asyncio.run(_reconcile(cfg, args.apply))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
