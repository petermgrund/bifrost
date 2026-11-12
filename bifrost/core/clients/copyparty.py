"""copyparty API client"""

from __future__ import annotations

import hashlib
from urllib.parse import quote, unquote

import httpx


class CopypartyError(Exception):
    """Wraps a failed call to copyparty"""

    def __init__(self, message: str, status: int = 0) -> None:
        super().__init__(message)
        self.status = status


class CopypartyClient:
    def __init__(self, base_url: str, username: str = "", password: str = "") -> None:
        self._base = base_url.rstrip("/")
        secret = f"{username}:{password}" if username else password
        self._client = httpx.AsyncClient(
            timeout=30.0, follow_redirects=True, headers={"PW": secret} if secret else {})

    async def close(self) -> None:
        await self._client.aclose()

    def _url(self, path: str) -> str:
        return f"{self._base}/{quote(path.strip('/'))}"

    async def ls(self, folder: str = "") -> dict:
        """One folder's listing; a login copyparty did not accept reads as no access, so that is an error here"""
        where = f"/{folder.strip('/')}" if folder.strip("/") else "/"
        url = self._url(folder)
        resp = await self._client.get(f"{url}/?ls" if folder.strip("/") else f"{url}?ls")
        if resp.status_code >= 400:
            raise CopypartyError(f"GET {where}?ls → {resp.status_code}", resp.status_code)
        try:
            listing = resp.json()
        except ValueError:
            raise CopypartyError(f"GET {where}?ls did not answer with a listing")
        if "read" not in (listing.get("perms") or []):
            acct = listing.get("acct") or "*"
            who = "not signed in (check copyparty.username and password)" if acct == "*" else f"account {acct}"
            raise CopypartyError(f"{who} cannot read {where}", 403)
        return listing

    async def account(self, folder: str = "") -> str:
        """The account copyparty sees, once it can read the folder"""
        return (await self.ls(folder)).get("acct") or "*"

    async def walk(self, folder: str = "") -> list[dict]:
        """Every file under a folder as {path, size}; dotfiles and unfinished uploads are left out"""
        out: list[dict] = []
        todo = [folder.strip("/")]
        while todo:
            cur = todo.pop()
            listing = await self.ls(cur)
            for d in listing.get("dirs") or []:
                name = unquote(d.get("href") or "").strip("/")
                if name and not name.startswith("."):
                    todo.append(f"{cur}/{name}" if cur else name)
            for f in listing.get("files") or []:
                name = unquote((f.get("href") or "").split("?")[0])
                if not name or name.startswith(".") or name.endswith(".PARTIAL"):
                    continue
                out.append({"path": f"{cur}/{name}" if cur else name, "size": f.get("sz") or 0})
        out.sort(key=lambda f: f["path"])
        return out

    async def md5(self, path: str) -> str:
        """MD5 of a file's bytes, the checksum Gramps keeps for a media object"""
        digest = hashlib.md5(usedforsecurity=False)
        async with self._client.stream("GET", self._url(path),
                                       timeout=httpx.Timeout(30.0, read=300.0)) as resp:
            if resp.status_code >= 400:
                raise CopypartyError(f"GET /{path} → {resp.status_code}", resp.status_code)
            async for chunk in resp.aiter_bytes():
                digest.update(chunk)
        return digest.hexdigest()
