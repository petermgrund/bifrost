"""Single config: every service credential lives in one file.

Load order: $BIFROST_CONFIG if set, else config.yaml at the repo root.
The database path is resolved relative to the config file's directory, so the
same config works on the host (/opt/stacks/bifrost/) and in the container
(/app/).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class GrampsConfig:
    base_url: str
    username: str
    password: str


@dataclass(frozen=True)
class ImmichConfig:
    base_url: str
    api_key: str


@dataclass(frozen=True)
class PaperlessConfig:
    base_url: str
    api_token: str


@dataclass(frozen=True)
class FacesConfig:
    # Write-through export of person links in the legacy person_map.yaml
    # format, kept until Phase 2 retires immich_to_gramps.py --link-faces
    # (which reads it). None disables the export.
    person_map_export: Path | None = None


@dataclass(frozen=True)
class Config:
    gramps: GrampsConfig
    immich: ImmichConfig
    paperless: PaperlessConfig
    db_path: Path
    config_path: Path
    faces: FacesConfig = FacesConfig()


DEFAULT_PATH = Path(__file__).resolve().parents[2] / "config.yaml"


def load_config(path: str | Path | None = None) -> Config:
    cfg_path = Path(path or os.environ.get("BIFROST_CONFIG") or DEFAULT_PATH)
    if not cfg_path.is_file():
        raise ConfigError(
            f"Config not found at {cfg_path} — copy config.example.yaml and fill it in"
        )
    raw = yaml.safe_load(cfg_path.read_text()) or {}

    def section(name: str, fields: list[str]) -> dict:
        block = raw.get(name) or {}
        missing = [f for f in fields if not block.get(f)]
        if missing:
            raise ConfigError(f"Config section '{name}' missing: {', '.join(missing)}")
        return {f: block[f] for f in fields}

    db = Path(raw.get("database") or "data/bifrost.db")
    if not db.is_absolute():
        db = cfg_path.parent / db
    faces_raw = raw.get("faces") or {}
    export = faces_raw.get("person_map_export")
    return Config(
        gramps=GrampsConfig(**section("gramps", ["base_url", "username", "password"])),
        immich=ImmichConfig(**section("immich", ["base_url", "api_key"])),
        paperless=PaperlessConfig(**section("paperless", ["base_url", "api_token"])),
        db_path=db,
        config_path=cfg_path,
        faces=FacesConfig(person_map_export=Path(export) if export else None),
    )
