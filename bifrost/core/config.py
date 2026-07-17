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
class ImmichConfig:
    # Optional section — when empty, the Immich sync endpoint answers 503.
    base_url: str = ""
    api_key: str = ""


@dataclass(frozen=True)
class SyncImmichConfig:
    # Dev-safety knob (was urd's empty bifrost.base_url): false disables the
    # Sync section's Immich block and 503s the apply + single-asset sync
    # endpoints (preview stays readable), so a dev instance pointed at
    # production can't create objects in the real tree.
    enabled: bool = True
    public_url: str = ""
    # ((immich_prefix, gramps_prefix), ...) — first prefix match wins;
    # an originalPath matching none is a hard sync error, never a guess.
    path_mappings: tuple[tuple[str, str], ...] = ()
    # The face-linker's person_map.yaml (it owns person links since 2026-07-01).
    person_map_path: Path | None = None
    # The gda.* KV keys on Immich assets (core/gda) — shared by the Photos
    # page and the Immich sync, configured in this one section only.
    date_key: str = "gda.date"
    scan_key: str = "gda.scan"
    gramps_key: str = "gda.gramps"
    verso_key: str = "gda.verso"


@dataclass(frozen=True)
class SyncPaperlessConfig:
    sync_tags: tuple[str, ...] = ("doc", "img")
    public_url: str = ""
    gramps_public_url: str = ""
    gramps_id_field_id: int = 0
    gramps_url_field_id: int = 0
    date_qualifier_field_id: int | None = None
    source_url_field_id: int | None = None
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
    immich: ImmichConfig = ImmichConfig()
    sync_immich: SyncImmichConfig = SyncImmichConfig()
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
        source_url_field_id=sp_raw.get("source_url_field_id"),
        transcription_tag_id=sp_raw.get("transcription_tag_id"),
        ocr_tag=sp_raw.get("ocr_tag") or "",
    )
    im_raw = raw.get("immich") or {}
    si_raw = (raw.get("sync") or {}).get("immich") or {}
    sync_immich = SyncImmichConfig(
        enabled=si_raw.get("enabled") is not False,
        public_url=(si_raw.get("public_url") or "").rstrip("/"),
        path_mappings=tuple(
            (m["immich_prefix"], m["gramps_prefix"])
            for m in (si_raw.get("path_mappings") or [])
        ),
        person_map_path=Path(p) if (p := si_raw.get("person_map_path")) else None,
        date_key=si_raw.get("date_key") or "gda.date",
        scan_key=si_raw.get("scan_key") or "gda.scan",
        gramps_key=si_raw.get("gramps_key") or "gda.gramps",
        verso_key=si_raw.get("verso_key") or "gda.verso",
    )
    gem_raw = raw.get("gemini") or {}
    return Config(
        gramps=GrampsConfig(**section("gramps", ["base_url", "username", "password"])),
        paperless=PaperlessConfig(**section("paperless", ["base_url", "api_token"])),
        db_path=db,
        config_path=cfg_path,
        immich=ImmichConfig(
            base_url=(im_raw.get("base_url") or "").rstrip("/"),
            api_key=im_raw.get("api_key") or "",
        ),
        sync_immich=sync_immich,
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
