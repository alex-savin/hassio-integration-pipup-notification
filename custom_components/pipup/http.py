"""HTTP endpoint that turns PiPup delivery callbacks into Home Assistant events.

PiPup fires a fire-and-forget POST to a ``callback`` URL as a popup progresses:

* ``{"event": "shown", "id": ...}`` / ``{"event": "dismissed", "id": ...}``
* ``{"event": "button", "id": ..., "button": ..., "label": ...}`` when a button is pressed.

The integration auto-points that ``callback`` at ``/api/pipup/callback/<entry_id>`` (see
``notify.py``), so this view can tie a callback back to the TV that produced it and re-emit it on
the Home Assistant event bus — a ``pipup_button`` event for presses, ``pipup_callback`` otherwise.
"""

from __future__ import annotations

import hmac
from http import HTTPStatus

from aiohttp import web

from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import (
    CALLBACK_PATH,
    DATA_CALLBACK_TOKENS,
    DATA_CALLBACK_VIEW,
    DOMAIN,
    EVENT_BUTTON,
    EVENT_CALLBACK,
)


@callback
def async_register_callback_view(hass: HomeAssistant) -> None:
    """Register the shared callback view exactly once for the integration."""
    if hass.data.get(DATA_CALLBACK_VIEW):
        return
    hass.http.register_view(PipupCallbackView())
    hass.data[DATA_CALLBACK_VIEW] = True


class PipupCallbackView(HomeAssistantView):
    """Receives PiPup's unauthenticated delivery/button callbacks from the TV."""

    url = CALLBACK_PATH + "/{entry_id}"
    name = "api:pipup:callback"
    # The TV cannot present a Home Assistant token, so this endpoint is unauthenticated; instead each
    # request must carry the per-entry secret we handed the TV in the callback URL (checked below).
    requires_auth = False

    async def post(self, request: web.Request, entry_id: str) -> web.Response:
        """Handle one callback POST and fire the matching event."""
        hass: HomeAssistant = request.app[KEY_HASS]

        # Reject anything not carrying this entry's secret (unknown entry, missing/wrong token) with the
        # same response, so the endpoint can't be used to forge button events or enumerate entry ids.
        expected = hass.data.get(DATA_CALLBACK_TOKENS, {}).get(entry_id)
        provided = request.query.get("token")
        if not expected or not provided or not hmac.compare_digest(expected, provided):
            return self.json_message("forbidden", HTTPStatus.FORBIDDEN)

        try:
            data = await request.json()
        except ValueError:
            return self.json_message("invalid json", HTTPStatus.BAD_REQUEST)
        if not isinstance(data, dict):
            return self.json_message("expected a json object", HTTPStatus.BAD_REQUEST)

        device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry_id)})
        base = {
            "entry_id": entry_id,
            "device_id": device.id if device else None,
            "popup_id": data.get("id"),
        }
        if data.get("event") == "button":
            hass.bus.async_fire(
                EVENT_BUTTON,
                {**base, "button": data.get("button"), "label": data.get("label")},
            )
        else:
            hass.bus.async_fire(EVENT_CALLBACK, {**base, "event": data.get("event")})
        return self.json({"status": "ok"})
