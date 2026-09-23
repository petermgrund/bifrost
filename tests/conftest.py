import secrets
from types import SimpleNamespace

import pytest

from bifrost.core import ids


@pytest.fixture
def script_ids(monkeypatch):
    """Make generate_gramps_id propose the given candidates first, in order"""
    def script(*candidates):
        queue = list("".join(candidates))
        monkeypatch.setattr(ids, "secrets", SimpleNamespace(
            choice=lambda seq: queue.pop(0) if queue else secrets.choice(seq)))
    return script
