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
    # parent tag for the ID/{gramps_id} write-back
    id_tag_prefix: str = "ID"
    gramps_public_url: str = ""
    # account labels the Photos section browses
    photos_accounts: tuple[str, ...] = ()


@dataclass(frozen=True)
class SyncPaperlessConfig:
    sync_tags: tuple[str, ...] = ("doc", "img")
    public_url: str = ""
    gramps_public_url: str = ""
    gramps_id_field_id: int = 0
    gramps_url_field_id: int = 0
    date_qualifier_field_id: int | None = None
    transcription_tag_id: int | None = None
    ocr_tag: str = ""
    webhook_token: str = ""
    # Paperless custom field id -> the Gramps media attribute that mirrors it
    attribute_fields: tuple[tuple[int, str], ...] = ()


@dataclass(frozen=True)
class GeminiConfig:
    api_key: str = ""
    model: str = "gemini-3-flash-preview"
    thinking_budget: int | None = None


# the words a `Cited for` row may hold: the Gramps event type in lower case for a dated fact,
# and these for everything else (house style, Part A)
DEFAULT_CITED_FOR = (
    "identity", "name", "birth", "birthplace", "age", "baptism", "confirmation",
    "mother", "father", "parents", "child", "spouse", "marriage", "divorce",
    "death", "burial", "residence", "household", "census", "occupation",
    "emigration", "immigration", "naturalization", "military", "muster",
    "property", "probate", "inventory", "will", "depicts", "place",
)

# words an attached event of this type accounts for, beyond its own name in lower case
DEFAULT_CLAIM_WORDS = (
    ("Birth", ("birth", "birthplace", "age")),
    ("Baptism", ("baptism",)),
    ("Christening", ("baptism",)),
    ("Burial", ("burial",)),
    ("Cremation", ("burial",)),
    ("Marriage", ("marriage", "spouse")),
    ("Marriage Banns", ("marriage",)),
    ("Residence", ("residence", "household")),
    ("Census", ("census", "household", "residence")),
    ("Probate", ("probate", "inventory", "will")),
    ("Military Service", ("military", "muster")),
)

DEFAULT_EVIDENCE_TAGS = (
    ("unproven", "Unproven"), ("conflict", "Conflict"), ("lapse", "Lapse"), ("disproven", "Disproven"))


@dataclass(frozen=True)
class EvidenceConfig:
    """The Evidence section: claims, proofs and audits over the citations in Gramps"""
    enabled: bool = False
    cited_for: tuple[str, ...] = DEFAULT_CITED_FOR
    claim_words: tuple[tuple[str, tuple[str, ...]], ...] = DEFAULT_CLAIM_WORDS
    tags: tuple[tuple[str, str], ...] = DEFAULT_EVIDENCE_TAGS

    def tag(self, status: str) -> str:
        return dict(self.tags)[status]


@dataclass(frozen=True)
class Config:
    gramps: GrampsConfig
    paperless: PaperlessConfig
    db_path: Path
    config_path: Path
    immich: ImmichConfig = ImmichConfig()
    sync_immich: SyncImmichConfig = SyncImmichConfig()
    sync_paperless: SyncPaperlessConfig = SyncPaperlessConfig()
    gemini: GeminiConfig = GeminiConfig()
    evidence: EvidenceConfig = EvidenceConfig()


# attributes the Paperless sync writes for its own purposes; a mirrored field may not take their names
SYNC_ATTRIBUTES = frozenset({"Paperless ID", "Paperless URL"})


def parse_attribute_fields(block: dict) -> tuple[tuple[int, str], ...]:
    """sync.paperless.attribute_fields, a mapping of custom field id to attribute name, checked:
    numeric ids, non-empty names, nothing listed twice, no key field and no name the sync owns"""
    raw = block.get("attribute_fields")
    if raw is None or raw == {}:
        return ()
    if not isinstance(raw, dict):
        raise ConfigError("sync.paperless.attribute_fields must map Paperless field ids to attribute names")
    keys = set()
    for key in ("gramps_id_field_id", "gramps_url_field_id"):
        try:
            if block.get(key) not in (None, ""):
                keys.add(int(block[key]))
        except (TypeError, ValueError):
            pass
    out: list[tuple[int, str]] = []
    for field, name in raw.items():
        try:
            fid = int(field)
        except (TypeError, ValueError):
            raise ConfigError(f"sync.paperless.attribute_fields: {field!r} is not a numeric field id")
        text = " ".join(str(name or "").split())
        if not text:
            raise ConfigError(f"sync.paperless.attribute_fields: field {fid} needs an attribute name")
        if fid in keys:
            raise ConfigError(f"sync.paperless.attribute_fields: field {fid} is a key field, not one to mirror")
        if text in SYNC_ATTRIBUTES:
            raise ConfigError(f"sync.paperless.attribute_fields: {text!r} is written by the sync itself")
        if any(f == fid or n == text for f, n in out):
            raise ConfigError(f"sync.paperless.attribute_fields: field {fid} or {text!r} is listed twice")
        out.append((fid, text))
    return tuple(out)


def _words(raw, where: str) -> tuple[str, ...]:
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, (list, tuple)):
        raise ConfigError(f"{where} must be a list of words")
    out: list[str] = []
    for w in raw:
        word = " ".join(str(w or "").split()).lower()
        if not word or "," in word or ";" in word or ":" in word:
            raise ConfigError(f"{where}: {w!r} is not a single word")
        if word not in out:
            out.append(word)
    return tuple(out)


def parse_evidence(block: dict) -> EvidenceConfig:
    """The evidence block: a switch, the `Cited for` vocabulary, the words an event type accounts
    for, and the four status tags. Every claim word must be in the vocabulary"""
    if block is None:
        return EvidenceConfig()
    if not isinstance(block, dict):
        raise ConfigError("evidence must be a mapping")
    cited_for = (_words(block["cited_for"], "evidence.cited_for")
                 if block.get("cited_for") is not None else DEFAULT_CITED_FOR)
    claim_words: list[tuple[str, tuple[str, ...]]] = []
    raw_words = block.get("claim_words")
    if raw_words is None:
        claim_words = list(DEFAULT_CLAIM_WORDS)
    elif not isinstance(raw_words, dict):
        raise ConfigError("evidence.claim_words must map event types to lists of words")
    else:
        for etype, words in raw_words.items():
            claim_words.append((str(etype).strip(), _words(words, f"evidence.claim_words.{etype}")))
    for etype, words in claim_words:
        for w in words:
            if w not in cited_for:
                raise ConfigError(f"evidence.claim_words.{etype}: {w!r} is not in evidence.cited_for")
    tags = dict(DEFAULT_EVIDENCE_TAGS)
    raw_tags = block.get("tags")
    if raw_tags is not None:
        if not isinstance(raw_tags, dict):
            raise ConfigError("evidence.tags must map unproven/conflict/lapse/disproven to tag names")
        for status, name in raw_tags.items():
            if status not in tags:
                raise ConfigError(f"evidence.tags: unknown status {status!r}")
            text = " ".join(str(name or "").split())
            if not text:
                raise ConfigError(f"evidence.tags.{status} needs a tag name")
            tags[status] = text
    if len(set(tags.values())) != len(tags):
        raise ConfigError("evidence.tags: two statuses share a tag name")
    return EvidenceConfig(
        enabled=bool(block.get("enabled", False)),
        cited_for=cited_for,
        claim_words=tuple(claim_words),
        tags=tuple(tags.items()),
    )


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
        transcription_tag_id=int_or_none(sp_raw, "sync.paperless", "transcription_tag_id"),
        ocr_tag=sp_raw.get("ocr_tag") or "",
        webhook_token=str(sp_raw.get("webhook_token") or "").strip(),
        attribute_fields=parse_attribute_fields(sp_raw),
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
        id_tag_prefix=str(si_raw.get("id_tag_prefix", "ID") or "").strip().strip("/"),
        gramps_public_url=(si_raw.get("gramps_public_url")
                           or sp_raw.get("gramps_public_url") or "").rstrip("/"),
        photos_accounts=tuple(
            str(x).strip() for x in (
                [si_raw["photos_accounts"]] if isinstance(si_raw.get("photos_accounts"), str)
                else si_raw.get("photos_accounts") or [])
            if str(x).strip()),
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
        gemini=GeminiConfig(
            api_key=gem_raw.get("api_key") or "",
            model=gem_raw.get("model") or "gemini-3-flash-preview",
            thinking_budget=gem_raw.get("thinking_budget"),
        ),
        evidence=parse_evidence(raw.get("evidence")),
    )
