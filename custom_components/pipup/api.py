"""Minimal async client for the PiPup HTTP API."""

from __future__ import annotations

import asyncio
from typing import Any

from aiohttp import ClientError, ClientSession

from .const import DEFAULT_TIMEOUT


class PipupError(Exception):
    """Base PiPup error."""


class PipupConnectionError(PipupError):
    """Raised when the device cannot be reached."""


class PipupAuthError(PipupError):
    """Raised when authentication fails (HTTP 401)."""


class PipupClient:
    """Talks to a single PiPup server over its local HTTP API."""

    def __init__(
        self,
        session: ClientSession,
        host: str,
        port: int,
        token: str | None = None,
    ) -> None:
        """Initialise the client."""
        self._session = session
        self._host = host
        self._port = port
        self._token = token or None

    @property
    def base_url(self) -> str:
        """Return the base URL of the device."""
        return f"http://{self._host}:{self._port}"

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"} if self._token else {}

    async def async_ping(self) -> str:
        """Return the plain-text reachability response, e.g. ``pipup 0.2.2``."""
        return await self._request("GET", "/ping", auth=False)

    async def async_status(self) -> dict[str, Any]:
        """Return the JSON status snapshot (version, active, count, authEnabled...)."""
        return await self._request("GET", "/status", auth=False, as_json=True)

    async def async_notify(self, payload: dict[str, Any]) -> None:
        """Show a notification on the TV."""
        await self._request("POST", "/notify", json_body=payload, auth=True)

    async def async_cancel(self) -> None:
        """Dismiss all on-screen notifications."""
        await self._request("POST", "/cancel", auth=True)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        auth: bool = True,
        as_json: bool = False,
    ) -> Any:
        url = f"{self.base_url}{path}"
        headers = self._auth_headers() if auth else {}
        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                response = await self._session.request(
                    method, url, json=json_body, headers=headers
                )
        except (ClientError, asyncio.TimeoutError) as err:
            raise PipupConnectionError(f"Could not reach {url}: {err}") from err

        if response.status == 401:
            raise PipupAuthError("Authentication failed (check the token)")
        if response.status >= 400:
            text = await response.text()
            raise PipupError(f"HTTP {response.status}: {text.strip()}")

        if as_json:
            return await response.json()
        return await response.text()
