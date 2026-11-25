"""Per-popup callback tokens, and the webhook that turns PiPup callbacks into Home Assistant events.

When a popup has buttons, the integration points its ``callback`` at a local-only webhook with a
token minted for that one popup. The app POSTs ``{"event": "shown"|"dismissed", "id"}`` and
``{"event": "button", "id", "button", "label"}`` there.

A token is bound to what Home Assistant showed: the popup id, its buttons and the TV. The fired
event is built from that record, never from the request body, so a token seen on the network cannot
be turned into a press of another button, popup or TV. It accepts one button press, ends with the
popup's ``dismissed`` callback, and expires on its own a while after the popup's duration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import secrets
from typing import Any

from aiohttp import web

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import (
    CALLBACK_TOKEN_GRACE,
    CALLBACK_TOKEN_MIN_TTL,
    CALLBACK_TOKEN_STICKY_TTL,
    DATA_CALLBACK_TOKENS,
    EVENT_BUTTON,
    EVENT_CALLBACK,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class CallbackToken:
    """What one popup's callback is allowed to report."""

    entry_id: str
    device_id: str | None
    popup_id: str
    buttons: dict[str, str]  # button id -> label
    expires: datetime
    pressed: bool = field(default=False)


def token_ttl(duration: int | None) -> timedelta:
    """How long a popup's token lives: its duration plus a grace period, at least 15 minutes.

    A sticky popup (duration 0 or less) can sit on screen for days, so it gets a long TTL; its token
    still ends with the popup's ``dismissed`` callback.
    """
    if duration is not None and duration <= 0:
        return CALLBACK_TOKEN_STICKY_TTL
    seconds = 30 if duration is None else duration  # the app's default duration
    return max(timedelta(seconds=seconds) + CALLBACK_TOKEN_GRACE, CALLBACK_TOKEN_MIN_TTL)


def _tokens(hass: HomeAssistant) -> dict[str, CallbackToken]:
    return hass.data.setdefault(DATA_CALLBACK_TOKENS, {})


def issue_token(
    hass: HomeAssistant,
    *,
    entry_id: str,
    device_id: str | None,
    popup_id: str,
    buttons: list[dict[str, Any]],
    duration: int | None,
) -> str:
    """Mint a token for one popup and remember what it may report. Sweeps expired tokens."""
    tokens = _tokens(hass)
    now = dt_util.utcnow()
    for stale in [tok for tok, rec in tokens.items() if rec.expires < now]:
        tokens.pop(stale, None)
    token = secrets.token_urlsafe(24)
    tokens[token] = CallbackToken(
        entry_id=entry_id,
        device_id=device_id,
        popup_id=popup_id,
        buttons={str(b["id"]): str(b.get("label", "")) for b in buttons},
        expires=now + token_ttl(duration),
    )
    return token


def drop_entry_tokens(hass: HomeAssistant, entry_id: str) -> None:
    """Forget every token issued for a TV (its entry is being unloaded)."""
    tokens = _tokens(hass)
    for tok in [tok for tok, rec in tokens.items() if rec.entry_id == entry_id]:
        tokens.pop(tok, None)


def handle_callback(
    hass: HomeAssistant, entry_id: str, token: str | None, data: Any
) -> bool:
    """Validate one callback and fire the matching event. Returns whether it was accepted."""
    tokens = _tokens(hass)
    record = tokens.get(token) if token else None
    if record is None or record.entry_id != entry_id or record.expires < dt_util.utcnow():
        if record is not None:
            tokens.pop(token, None)  # expired, or presented on another TV's webhook
        _LOGGER.warning("Rejected a PiPup callback with a missing, unknown or expired token")
        return False
    if not isinstance(data, dict):
        return False

    base = {
        "entry_id": record.entry_id,
        "device_id": record.device_id,
        "popup_id": record.popup_id,
    }
    event = data.get("event")
    if event == "button":
        button = str(data.get("button"))
        if record.pressed or button not in record.buttons:
            _LOGGER.warning(
                "Rejected a PiPup button callback for popup %s: %s",
                record.popup_id,
                "already pressed" if record.pressed else f"button {button!r} was not on it",
            )
            return False
        record.pressed = True
        hass.bus.async_fire(
            EVENT_BUTTON, {**base, "button": button, "label": record.buttons[button]}
        )
        return True
    if event in ("shown", "dismissed"):
        if event == "dismissed":
            tokens.pop(token, None)
        hass.bus.async_fire(EVENT_CALLBACK, {**base, "event": event})
        return True
    return False


async def async_handle_callback_webhook(
    hass: HomeAssistant, webhook_id: str, request: web.Request, entry_id: str
) -> web.Response:
    """Webhook handler (bound to one config entry with functools.partial)."""
    try:
        data = await request.json()
    except ValueError:
        return web.Response(status=400)
    accepted = handle_callback(hass, entry_id, request.query.get("token"), data)
    return web.Response(status=200 if accepted else 403)
