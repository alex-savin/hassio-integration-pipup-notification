"""Minimal async client for the PiPup HTTP API."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from aiohttp import ClientError, ClientSession, FormData

from .const import DEFAULT_TIMEOUT


class PipupError(Exception):
    """Base PiPup error."""


class PipupConnectionError(PipupError):
    """Raised when the device cannot be reached."""


class PipupAuthError(PipupError):
    """Raised when authentication fails (HTTP 401)."""


class PipupNotSupportedError(PipupError):
    """Raised when the app on the TV is too old for a request (HTTP 404 on a newer endpoint)."""


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

    async def async_notify(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Show a notification on the TV; returns the app's answer (``{"status", "id"}``)."""
        return await self._request(
            "POST", "/notify", json_body=payload, auth=True, as_json=True
        )

    async def async_notify_image(
        self,
        fields: dict[str, Any],
        image: bytes,
        content_type: str = "image/jpeg",
        width: int | None = None,
    ) -> dict[str, Any]:
        """Show a notification with an uploaded image (multipart ``/notify``).

        Only scalar fields travel over multipart; nested ones (media, buttons) are JSON-only.
        """
        form = FormData()
        for key, value in fields.items():
            if isinstance(value, (dict, list)) or value is None:
                continue
            form.add_field(key, str(value).lower() if isinstance(value, bool) else str(value))
        if width is not None:
            form.add_field("imageWidth", str(width))
        form.add_field("image", image, filename="snapshot.jpg", content_type=content_type)
        return await self._request("POST", "/notify", data=form, auth=True, as_json=True)

    async def async_cancel(self, popup_id: str | None = None) -> None:
        """Dismiss one popup by id, or every popup on screen."""
        params = {"id": popup_id} if popup_id else None
        await self._request("POST", "/cancel", params=params, auth=True)

    async def async_power_on(self) -> bool | None:
        """Turn the screen on (and end a screensaver). App 0.4.0+.

        Returns whether the screen actually came on (app 0.5.0+ reports ``reached``), or None when the
        app only confirms that it tried (0.4.x answers a plain ``ok``).
        """
        answer = await self._request(
            "POST", "/power", params={"state": "on"}, auth=True, newer_endpoint=True
        )
        try:
            body = json.loads(answer)
        except ValueError:
            return None
        reached = body.get("reached") if isinstance(body, dict) else None
        return reached if isinstance(reached, bool) else None

    async def async_set_push(self, url: str) -> dict[str, Any]:
        """Point the app's state pushes at ``url``; an empty string turns pushing off. App 0.4.0+."""
        return await self._request(
            "POST",
            "/push",
            params={"url": url},
            auth=True,
            as_json=True,
            newer_endpoint=True,
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        data: Any = None,
        params: dict[str, str] | None = None,
        auth: bool = True,
        as_json: bool = False,
        newer_endpoint: bool = False,
    ) -> Any:
        url = f"{self.base_url}{path}"
        headers = self._auth_headers() if auth else {}
        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                response = await self._session.request(
                    method, url, json=json_body, data=data, params=params, headers=headers
                )
                if response.status == 401:
                    raise PipupAuthError("Authentication failed (check the token)")
                if response.status == 404 and newer_endpoint:
                    raise PipupNotSupportedError(
                        f"{path} is not supported by this PiPup app version"
                    )
                if response.status >= 400:
                    text = await response.text()
                    raise PipupError(f"HTTP {response.status}: {text.strip()}")
                if as_json:
                    return await response.json(content_type=None)
                return await response.text()
        except (ClientError, TimeoutError) as err:
            raise PipupConnectionError(f"Could not reach {url}: {err}") from err
        except ValueError as err:  # a non-JSON body where JSON was expected
            raise PipupError(f"Unexpected answer from {url}: {err}") from err
