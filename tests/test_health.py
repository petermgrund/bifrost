"""Service probes"""

import asyncio

from bifrost.core import health


class FakeGramps:
    def __init__(self, meta=None, boom=None):
        self._meta, self._boom = meta or {}, boom

    async def get_metadata(self):
        if self._boom:
            raise RuntimeError(self._boom)
        return self._meta


class FakePaperless:
    def __init__(self, version="3.0.5", boom=None):
        self._version, self._boom = version, boom

    async def version(self):
        if self._boom:
            raise RuntimeError(self._boom)
        return self._version


class FakeImmich:
    def __init__(self, label, me=None, boom=None, version="3.1.0"):
        self.label, self._me, self._boom = label, me or {}, boom
        self._version = version

    async def get_me(self):
        if self._boom:
            raise RuntimeError(self._boom)
        return self._me

    async def server_version(self):
        if self._boom:
            raise RuntimeError(self._boom)
        return self._version


GRAMPS_META = {"database": {"name": "Test Tree"}, "gramps_webapi": {"version": "3.20.1"}}


def _probe(gramps, paperless, accounts):
    return asyncio.run(health.probe_services(gramps, paperless, accounts))


def test_all_services_reachable():
    rows = _probe(
        FakeGramps(GRAMPS_META), FakePaperless(),
        [FakeImmich("fh", {"email": "fh@example.com"}),
         FakeImmich("peter", {"email": "peter@example.com"})])
    by_key = {r["key"]: r for r in rows}
    assert all(r["ok"] for r in rows)
    # the tick means authenticated; the detail is only the version
    assert by_key["gramps"]["detail"] == "v3.20.1"
    assert by_key["paperless"]["detail"] == "v3.0.5"
    assert by_key["immich:fh"]["name"] == "Immich (fh)"
    assert by_key["immich:fh"]["detail"] == "v3.1.0"
    assert "fh@example.com" not in by_key["immich:fh"]["detail"]
    assert [r["key"] for r in rows] == [
        "gramps", "paperless", "immich:fh", "immich:peter"]


def test_a_failure_is_reported_not_raised():
    rows = _probe(FakeGramps(boom="connection refused"), FakePaperless(),
                  [FakeImmich("fh", {"email": "x@y.z"})])
    gramps = next(r for r in rows if r["key"] == "gramps")
    assert gramps["ok"] is False and "connection refused" in gramps["detail"]
    assert next(r for r in rows if r["key"] == "paperless")["ok"] is True


def test_every_account_is_probed_independently():
    rows = _probe(FakeGramps(GRAMPS_META), FakePaperless(),
                  [FakeImmich("fh", {"email": "ok@y.z"}),
                   FakeImmich("peter", boom="401 unauthorized")])
    assert next(r for r in rows if r["key"] == "immich:fh")["ok"] is True
    bad = next(r for r in rows if r["key"] == "immich:peter")
    assert bad["ok"] is False and "401" in bad["detail"]


def test_no_immich_accounts_reports_unconfigured():
    rows = _probe(FakeGramps(GRAMPS_META), FakePaperless(), [])
    immich = next(r for r in rows if r["key"] == "immich")
    assert immich["ok"] is False and "not configured" in immich["detail"].lower()
