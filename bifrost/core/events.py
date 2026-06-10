"""Typed events — the contract between domain modules and everything else.

Domain modules are async generators yielding SyncEvents. The web layer fans
them out to SSE and the run_events table; the CLI renders them as log lines.
Preview is the same generator run with apply=False, yielding would_* actions.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Literal

Kind = Literal["started", "item", "summary", "error"]
Entity = Literal["media", "face", "note", "place", "doc"]
Action = Literal[
    "created", "updated", "skipped", "failed", "would_create", "would_update"
]


@dataclass
class SyncEvent:
    kind: Kind
    entity: Entity | None = None
    action: Action | None = None
    source_id: str | None = None  # Immich UUID / Paperless ID / OSM relation
    gramps_id: str | None = None
    title: str | None = None
    detail: str | None = None
    data: dict | None = None  # structured extras (e.g. counts in summary)

    def to_json(self) -> str:
        return json.dumps(
            {k: v for k, v in asdict(self).items() if v is not None},
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, raw: str) -> "SyncEvent":
        return cls(**json.loads(raw))
