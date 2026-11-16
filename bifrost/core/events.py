from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Kind = Literal["started", "item", "summary", "error", "progress"]
Entity = Literal["media", "face", "note", "doc", "tag"]
Action = Literal[
    "created", "updated", "replaced", "removed", "skipped", "failed",
    "would_create", "would_update", "would_replace", "would_remove",
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


def progress(label: str, done: int, total: int) -> SyncEvent:
    """One running count over everything a scan touches"""
    return SyncEvent(kind="progress", detail=label,
                     data={"done": done, "total": total,
                           "percent": round(100 * done / total) if total else 100})
