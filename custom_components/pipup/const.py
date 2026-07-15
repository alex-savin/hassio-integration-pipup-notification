"""Constants for the PiPup integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "pipup"
PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.NOTIFY]

DEFAULT_PORT = 7979
DEFAULT_TIMEOUT = 10
SCAN_INTERVAL_SECONDS = 60

MANUFACTURER = "savin.nyc"
MODEL = "PiPup"

# Path (under Home Assistant's HTTP server) that receives PiPup delivery/button callbacks.
# The per-TV config entry id is appended so a callback can be tied back to its device.
CALLBACK_PATH = "/api/pipup/callback"

# Home Assistant event fired when a popup button is pressed on the TV.
EVENT_BUTTON = f"{DOMAIN}_button"
# Home Assistant event fired for the other lifecycle callbacks (shown / dismissed).
EVENT_CALLBACK = f"{DOMAIN}_callback"

# hass.data key marking that the (single, shared) callback HTTP view has been registered.
DATA_CALLBACK_VIEW = f"{DOMAIN}_callback_view"

# hass.data key -> {entry_id: secret}. The callback endpoint is unauthenticated (the TV can't present
# a HA token), so each callback URL carries this per-entry secret; the view rejects any request whose
# token doesn't match, which stops a client that never received the URL from forging button events.
DATA_CALLBACK_TOKENS = f"{DOMAIN}_callback_tokens"

# Service field name (Home Assistant) -> PiPup JSON key. Scalar fields only; `buttons` and `muted`
# are nested and handled explicitly in build_payload.
FIELD_MAP: dict[str, str] = {
    "title": "title",
    "message": "message",
    "id": "id",
    "duration": "duration",
    "position": "position",
    "tts": "tts",
    "sound": "sound",
    "background_color": "backgroundColor",
    "title_color": "titleColor",
    "title_size": "titleSize",
    "message_color": "messageColor",
    "message_size": "messageSize",
    "corner_radius": "cornerRadius",
    "border_color": "borderColor",
    "border_width": "borderWidth",
    "urgency": "urgency",
    "button_color": "buttonColor",
    "button_text_color": "buttonTextColor",
    "icon_uri": "iconUri",
    "show_progress": "showProgress",
    "replace": "replace",
    "callback": "callback",
    "media_position": "mediaPosition",
    "title_alignment": "titleAlignment",
    "message_alignment": "messageAlignment",
    "animation_type": "animationType",
    "animation_duration": "animationDuration",
    "animation_exit": "animationExit",
}
