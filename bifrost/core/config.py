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
class PaperlessConfig:
    base_url: str
    api_token: str


@dataclass(frozen=True)
class SyncPaperlessConfig:
    sync_tags: tuple[str, ...] = ("doc", "img")
    public_url: str = ""
    gramps_public_url: str = ""
    gramps_id_field_id: int = 0
    gramps_url_field_id: int = 0
    date_qualifier_field_id: int | None = None
    date_meaning_field_id: int | None = None
    transcription_tag_id: int | None = None
    ocr_tag: str = ""


@dataclass(frozen=True)
class PlacesConfig:
    osm_service_url: str = ""
    boundaries_dir: Path | None = None


@dataclass(frozen=True)
class AnthropicConfig:
    api_key: str = ""
    model: str = "claude-opus-4-8"


@dataclass(frozen=True)
class GeminiConfig:
    api_key: str = ""
    model: str = "gemini-3-flash-preview"
    thinking_budget: int | None = None


@dataclass(frozen=True)
class Config:
    gramps: GrampsConfig
    paperless: PaperlessConfig
    db_path: Path
    config_path: Path
    sync_paperless: SyncPaperlessConfig = SyncPaperlessConfig()
    anthropic: AnthropicConfig = AnthropicConfig()
    gemini: GeminiConfig = GeminiConfig()
    places: PlacesConfig = PlacesConfig()


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
    sp_raw = (raw.get("sync") or {}).get("paperless") or {}
    sync_paperless = SyncPaperlessConfig(
        sync_tags=tuple(sp_raw.get("sync_tags") or ("doc", "img")),
        public_url=(sp_raw.get("public_url") or "").rstrip("/"),
        gramps_public_url=(sp_raw.get("gramps_public_url") or "").rstrip("/"),
        gramps_id_field_id=int(sp_raw.get("gramps_id_field_id") or 0),
        gramps_url_field_id=int(sp_raw.get("gramps_url_field_id") or 0),
        date_qualifier_field_id=sp_raw.get("date_qualifier_field_id"),
        date_meaning_field_id=sp_raw.get("date_meaning_field_id"),
        transcription_tag_id=sp_raw.get("transcription_tag_id"),
        ocr_tag=sp_raw.get("ocr_tag") or "",
    )
    gem_raw = raw.get("gemini") or {}
    return Config(
        gramps=GrampsConfig(**section("gramps", ["base_url", "username", "password"])),
        paperless=PaperlessConfig(**section("paperless", ["base_url", "api_token"])),
        db_path=db,
        config_path=cfg_path,
        sync_paperless=sync_paperless,
        anthropic=AnthropicConfig(
            api_key=(raw.get("anthropic") or {}).get("api_key") or "",
            model=(raw.get("anthropic") or {}).get("model") or "claude-opus-4-8",
        ),
        gemini=GeminiConfig(
            api_key=gem_raw.get("api_key") or "",
            model=gem_raw.get("model") or "gemini-3-flash-preview",
            thinking_budget=gem_raw.get("thinking_budget"),
        ),
        places=PlacesConfig(
            osm_service_url=((raw.get("places") or {}).get("osm_service_url") or "").rstrip("/"),
            boundaries_dir=Path(b) if (b := (raw.get("places") or {}).get("boundaries_dir")) else None,
        ),
    )
