"""
    python -m bifrost.cli doctor
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from .core import db
from .core.clients import GrampsClient, PaperlessClient
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
