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

# Service field name (Home Assistant) -> PiPup JSON key.
FIELD_MAP: dict[str, str] = {
    "title": "title",
    "message": "message",
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
    "icon_uri": "iconUri",
    "show_progress": "showProgress",
    "replace": "replace",
    "callback": "callback",
}
