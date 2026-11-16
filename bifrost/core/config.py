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
    public_url: str = ""


@dataclass(frozen=True)
class PaperlessConfig:
    base_url: str = ""
    api_token: str = ""


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
    sync_tag: str = "Sync/Gramps"
    public_url: str = ""
    path_mappings: tuple[tuple[str, str], ...] = ()
    previews_prefix: str = ""
    # parent tag for the ID/{gramps_id} write-back
    id_tag_prefix: str = "ID"
    gramps_public_url: str = ""
    codes: bool = True


TRANSLATION_MARKER = "======== ENGLISH TRANSLATION ========"


@dataclass(frozen=True)
class SyncPaperlessConfig:
    sync_tags: tuple[str, ...] = ("sync",)
    public_url: str = ""
    gramps_public_url: str = ""
    gramps_id_field_id: int | str = 0
    gramps_url_field_id: int | str = 0
    date_qualifier_field_id: int | str | None = None
    transcription_tag_id: int | str | None = None
    ocr_tag: str = ""
    webhook_token: str = ""
    attribute_fields: tuple[tuple[int | str, str], ...] = ()
    # the line in a document's content after which its translation starts
    translation_marker: str = TRANSLATION_MARKER
    codes: bool = True


@dataclass(frozen=True)
class GeminiConfig:
    api_key: str = ""
    model: str = "gemini-3-flash-preview"
    thinking_budget: int | None = None


@dataclass(frozen=True)
class Config:
    gramps: GrampsConfig
    config_path: Path
    paperless: PaperlessConfig = PaperlessConfig()
    immich: ImmichConfig = ImmichConfig()
    sync_immich: SyncImmichConfig = SyncImmichConfig()
    sync_paperless: SyncPaperlessConfig = SyncPaperlessConfig()
    gemini: GeminiConfig = GeminiConfig()
    # False gives new media Gramps' own O numbers instead of codes
    codes: bool = True


SYNC_ATTRIBUTES = frozenset({"Paperless ID", "Paperless URL"})


def id_or_name(value) -> int | str | None:
    text = " ".join(str(value if value is not None else "").split())
    if not text:
        return None
    return int(text) if text.isdecimal() else text


def _same(a: int | str, b: int | str) -> bool:
    return str(a).casefold() == str(b).casefold()


def parse_attribute_fields(block: dict) -> tuple[tuple[int | str, str], ...]:
    raw = block.get("attribute_fields")
    if raw is None or raw == {}:
        return ()
    if not isinstance(raw, dict):
        raise ConfigError("paperless.attribute_fields must map Paperless fields to attribute names")
    keys = [k for k in (id_or_name(block.get("gramps_id_field")), id_or_name(block.get("gramps_url_field")))
            if k is not None]
    out: list[tuple[int | str, str]] = []
    for field, name in raw.items():
        fid = id_or_name(field)
        if fid is None:
            raise ConfigError("paperless.attribute_fields: a field has no name or id")
        text = " ".join(str(name or "").split())
        if not text:
            raise ConfigError(f"paperless.attribute_fields: field {fid} needs an attribute name")
        if any(_same(fid, k) for k in keys):
            raise ConfigError(f"paperless.attribute_fields: field {fid} is a key field, not one to mirror")
        if text in SYNC_ATTRIBUTES:
            raise ConfigError(f"paperless.attribute_fields: {text!r} is written by the sync itself")
        if any(_same(f, fid) or n == text for f, n in out):
            raise ConfigError(f"paperless.attribute_fields: field {fid} or {text!r} is listed twice")
        out.append((fid, text))
    return tuple(out)


DEFAULT_PATH = Path(__file__).resolve().parents[2] / "config.yaml"


def _url(block: dict, key: str) -> str:
    return str(block.get(key) or "").strip().rstrip("/")


def _required(raw: dict, name: str, fields: list[str]) -> dict:
    block = raw.get(name) or {}
    missing = [f for f in fields if not block.get(f)]
    if missing:
        raise ConfigError(f"Config section '{name}' missing: {', '.join(missing)}")
    return block


def _immich(im: dict, gramps_public_url: str, codes: bool) -> tuple[ImmichConfig, SyncImmichConfig]:
    accounts_raw = im.get("accounts") or []
    if not isinstance(accounts_raw, list) or len(accounts_raw) > 2:
        raise ConfigError("immich.accounts must be a list of 1 or 2 entries")
    accounts: list[ImmichAccount] = []
    for i, entry in enumerate(accounts_raw, 1):
        if not isinstance(entry, dict) or not entry.get("api_key"):
            raise ConfigError(f"immich.accounts entry {i} needs an api_key")
        accounts.append(ImmichAccount(api_key=entry["api_key"],
                                      label=(entry.get("label") or f"account {i}").strip()))
    mappings = []
    for m in im.get("path_mappings") or []:
        if not isinstance(m, dict) or "immich_prefix" not in m or "gramps_prefix" not in m:
            raise ConfigError(
                f"Each immich.path_mappings entry needs 'immich_prefix' and 'gramps_prefix' keys, got: {m!r}")
        mappings.append((m["immich_prefix"], m["gramps_prefix"]))
    previews_prefix = (im.get("previews_prefix") or "").strip()
    if previews_prefix and not previews_prefix.endswith("/"):
        previews_prefix += "/"
    return (
        ImmichConfig(base_url=_url(im, "base_url"), accounts=tuple(accounts)),
        SyncImmichConfig(
            sync_tag=(im.get("sync_tag") or "Sync/Gramps").strip() or "Sync/Gramps",
            public_url=_url(im, "public_url"),
            path_mappings=tuple(mappings),
            previews_prefix=previews_prefix,
            id_tag_prefix=str(im.get("id_tag_prefix", "ID") or "").strip().strip("/") if codes else "",
            gramps_public_url=gramps_public_url,
            codes=codes,
        ),
    )


def _paperless(pl: dict, gramps_public_url: str, codes: bool) -> SyncPaperlessConfig:
    return SyncPaperlessConfig(
        sync_tags=tuple(str(t).strip() for t in pl.get("sync_tags") or ("sync",) if str(t).strip()),
        public_url=_url(pl, "public_url"),
        gramps_public_url=gramps_public_url,
        gramps_id_field_id=id_or_name(pl.get("gramps_id_field")) or 0,
        gramps_url_field_id=id_or_name(pl.get("gramps_url_field")) or 0,
        date_qualifier_field_id=id_or_name(pl.get("date_qualifier_field")),
        transcription_tag_id=id_or_name(pl.get("transcribed_tag")),
        ocr_tag=str(pl.get("ocr_tag") or "").strip(),
        webhook_token=str(pl.get("webhook_token") or "").strip(),
        attribute_fields=parse_attribute_fields(pl),
        translation_marker=str(pl.get("translation_marker") or "").strip() or TRANSLATION_MARKER,
        codes=codes,
    )


def load_config(path: str | Path | None = None) -> Config:
    cfg_path = Path(path or os.environ.get("BIFROST_CONFIG") or DEFAULT_PATH)
    if cfg_path.is_dir():
        raise ConfigError(f"{cfg_path} is a directory, not a file")
    if not cfg_path.is_file():
        raise ConfigError(f"Config not found at {cfg_path}")
    raw = yaml.safe_load(cfg_path.read_text()) or {}
    if "sync" in raw:
        raise ConfigError(
            f"{cfg_path} has an old config layout")

    gramps = _required(raw, "gramps", ["base_url", "username", "password"])
    gramps_public_url = _url(gramps, "public_url")
    pl = _required(raw, "paperless", ["base_url", "api_token"]) if raw.get("paperless") else {}
    codes = raw.get("codes") is not False
    immich, sync_immich = _immich(raw.get("immich") or {}, gramps_public_url, codes)
    gem = raw.get("gemini") or {}
    return Config(
        gramps=GrampsConfig(base_url=gramps["base_url"], username=gramps["username"],
                            password=gramps["password"], public_url=gramps_public_url),
        config_path=cfg_path,
        paperless=PaperlessConfig(base_url=pl.get("base_url") or "", api_token=pl.get("api_token") or ""),
        immich=immich,
        sync_immich=sync_immich,
        sync_paperless=_paperless(pl, gramps_public_url, codes),
        gemini=GeminiConfig(
            api_key=gem.get("api_key") or "",
            model=gem.get("model") or "gemini-3-flash-preview",
            thinking_budget=gem.get("thinking_budget"),
        ),
        codes=codes,
    )
