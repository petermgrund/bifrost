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
class ImmichAccount:
    api_key: str
    label: str = ""


@dataclass(frozen=True)
class ImmichConfig:
    base_url: str = ""
    accounts: tuple[ImmichAccount, ...] = ()


@dataclass(frozen=True)
class SyncImmichConfig:
    enabled: bool = True
    sync_tag: str = "Sync/Gramps"
    public_url: str = ""
    path_mappings: tuple[tuple[str, str], ...] = ()
    previews_prefix: str = ""
    # temp legacy face-linker person_map.yaml
    person_map_path: Path | None = None
    place_tag_handle: str = ""
    # parent tag for the ID/{gramps_id} write-back; empty disables it
    id_tag_prefix: str = "ID"


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
    boundaries_dir: Path | None = None


@dataclass(frozen=True)
class CitationsConfig:
    house_style_path: Path | None = None


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
    citations: CitationsConfig = CitationsConfig()


DEFAULT_PATH = Path(__file__).resolve().parents[2] / "config.yaml"


def load_config(path: str | Path | None = None) -> Config:
    cfg_path = Path(path or os.environ.get("BIFROST_CONFIG") or DEFAULT_PATH)
    if cfg_path.is_dir():
        raise ConfigError(
            f"{cfg_path} is a directory, not a file"
        )
    if not cfg_path.is_file():
        raise ConfigError(
            f"Config not found at {cfg_path}"
        )
    raw = yaml.safe_load(cfg_path.read_text()) or {}

    def section(name: str, fields: list[str]) -> dict:
        block = raw.get(name) or {}
        missing = [f for f in fields if not block.get(f)]
        if missing:
            raise ConfigError(f"Config section '{name}' missing: {', '.join(missing)}")
        return {f: block[f] for f in fields}

    def int_or_none(block: dict, section_name: str, key: str) -> int | None:
        val = block.get(key)
        if val is None or val == "":
            return None
        try:
            return int(val)
        except (ValueError, TypeError):
            raise ConfigError(
                f"Config key '{section_name}.{key}' must be a numeric id "
                f"(or null), got {val!r}"
            )

    db = Path(raw.get("database") or "data/bifrost.db")
    if not db.is_absolute():
        db = cfg_path.parent / db
    sp_raw = (raw.get("sync") or {}).get("paperless") or {}
    sync_paperless = SyncPaperlessConfig(
        sync_tags=tuple(sp_raw.get("sync_tags") or ("doc", "img")),
        public_url=(sp_raw.get("public_url") or "").rstrip("/"),
        gramps_public_url=(sp_raw.get("gramps_public_url") or "").rstrip("/"),
        gramps_id_field_id=int_or_none(sp_raw, "sync.paperless", "gramps_id_field_id") or 0,
        gramps_url_field_id=int_or_none(sp_raw, "sync.paperless", "gramps_url_field_id") or 0,
        date_qualifier_field_id=int_or_none(sp_raw, "sync.paperless", "date_qualifier_field_id"),
        source_url_field_id=int_or_none(sp_raw, "sync.paperless", "source_url_field_id"),
        transcription_tag_id=int_or_none(sp_raw, "sync.paperless", "transcription_tag_id"),
        ocr_tag=sp_raw.get("ocr_tag") or "",
    )
    im_raw = raw.get("immich") or {}
    si_raw = (raw.get("sync") or {}).get("immich") or {}

    mappings = []
    for m in si_raw.get("path_mappings") or []:
        if not isinstance(m, dict) or "immich_prefix" not in m or "gramps_prefix" not in m:
            raise ConfigError(
                "Each sync.immich.path_mappings entry needs 'immich_prefix' "
                f"and 'gramps_prefix' keys, got: {m!r}"
            )
        mappings.append((m["immich_prefix"], m["gramps_prefix"]))
    previews_prefix = (si_raw.get("previews_prefix") or "").strip()
    if previews_prefix and not previews_prefix.endswith("/"):
        previews_prefix += "/"

    sync_immich = SyncImmichConfig(
        enabled=si_raw.get("enabled") is not False,
        sync_tag=(si_raw.get("sync_tag") or "Sync/Gramps").strip() or "Sync/Gramps",
        public_url=(si_raw.get("public_url") or "").rstrip("/"),
        path_mappings=tuple(mappings),
        previews_prefix=previews_prefix,
        person_map_path=Path(p) if (p := si_raw.get("person_map_path")) else None,
        place_tag_handle=(si_raw.get("place_tag_handle") or "").strip(),
        id_tag_prefix=str(si_raw.get("id_tag_prefix", "ID") or "").strip().strip("/"),
    )
    accounts_raw = im_raw.get("accounts")
    legacy_keys = [k for k in ("api_key", "partner_api_key") if im_raw.get(k)]
    if accounts_raw and legacy_keys:
        raise ConfigError(
            "immich: use either 'accounts' or the legacy "
            "api_key/partner_api_key keys, not both")
    immich_accounts: list[ImmichAccount] = []
    if accounts_raw:
        if not isinstance(accounts_raw, list) or not 1 <= len(accounts_raw) <= 2:
            raise ConfigError("immich.accounts must be a list of 1 or 2 entries")
        for i, entry in enumerate(accounts_raw, 1):
            if not isinstance(entry, dict) or not entry.get("api_key"):
                raise ConfigError(f"immich.accounts entry {i} needs an api_key")
            immich_accounts.append(ImmichAccount(
                api_key=entry["api_key"],
                label=(entry.get("label") or f"account {i}").strip()))
    else:
        # partner_api_key without api_key did nothing in the old scheme;
        # keep that so a legacy config cannot silently start syncing
        if im_raw.get("api_key"):
            immich_accounts.append(
                ImmichAccount(api_key=im_raw["api_key"], label="primary"))
            if im_raw.get("partner_api_key"):
                immich_accounts.append(
                    ImmichAccount(api_key=im_raw["partner_api_key"], label="partner"))

    gem_raw = raw.get("gemini") or {}
    return Config(
        gramps=GrampsConfig(**section("gramps", ["base_url", "username", "password"])),
        paperless=PaperlessConfig(**section("paperless", ["base_url", "api_token"])),
        db_path=db,
        config_path=cfg_path,
        immich=ImmichConfig(
            base_url=(im_raw.get("base_url") or "").rstrip("/"),
            accounts=tuple(immich_accounts),
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
            boundaries_dir=Path(b) if (b := (raw.get("places") or {}).get("boundaries_dir")) else None,
        ),
        citations=CitationsConfig(
            house_style_path=Path(p) if (p := (raw.get("citations") or {}).get("house_style_path")) else None,
        ),
    )
