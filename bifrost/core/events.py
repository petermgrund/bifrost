"""Typed events 
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
    source_id: str | None = None 
    gramps_id: str | None = None
    title: str | None = None
    detail: str | None = None
    data: dict | None = None

    def to_json(self) -> str:
        return json.dumps(
            {k: v for k, v in asdict(self).items() if v is not None},
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, raw: str) -> "SyncEvent":
        return cls(**json.loads(raw))
