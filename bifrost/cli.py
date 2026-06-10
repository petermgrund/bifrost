"""Bifrost CLI — thin entry points for setup and cron.

    python -m bifrost.cli doctor          # connectivity + auth check, all services
    python -m bifrost.cli import-legacy   # one-shot import of legacy state files
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from .core import db
from .core.clients import GrampsClient, ImmichClient, PaperlessClient
from .core.config import Config, ConfigError, load_config


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

    async def check_immich() -> tuple[str, bool, str]:
        try:
            async with ImmichClient(cfg.immich.base_url, cfg.immich.api_key) as ic:
                me = await ic.get_me()
            return _ok("immich", f"authenticated as {me.get('name') or me.get('email') or '?'}")
        except Exception as exc:  # noqa: BLE001
            return _fail("immich", exc)

    async def check_paperless() -> tuple[str, bool, str]:
        try:
            async with PaperlessClient(cfg.paperless.base_url, cfg.paperless.api_token) as pc:
                n = await pc.count_tags()
            return _ok("paperless", f"authenticated, {n} tags")
        except Exception as exc:  # noqa: BLE001
            return _fail("paperless", exc)

    checks.extend(await asyncio.gather(check_gramps(), check_immich(), check_paperless()))

    width = max(len(label) for label, _, _ in checks)
    failed = False
    for label, ok, detail in checks:
        mark = "ok  " if ok else "FAIL"
        print(f"  {label.ljust(width)}  {mark}  {detail}")
        failed = failed or not ok
    return 1 if failed else 0


def _import_legacy(cfg: Config) -> int:
    from .modules.import_legacy import import_all

    conn = db.connect(cfg.db_path)
    result = import_all(conn)
    conn.close()
    for table, n in result.counts.items():
        print(f"  {table}: {n} rows")
    for miss in result.missing:
        print(f"  MISSING {miss}")
    return 1 if result.missing else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bifrost")
    parser.add_argument("--config", help="path to config.yaml (default: $BIFROST_CONFIG or repo root)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="connectivity + auth check against all services")
    sub.add_parser("import-legacy", help="import legacy state files into SQLite")
    args = parser.parse_args(argv)

    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    if args.command == "doctor":
        return asyncio.run(_doctor(cfg))
    if args.command == "import-legacy":
        return _import_legacy(cfg)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
