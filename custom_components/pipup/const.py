"""Constants for the PiPup integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "pipup"
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NOTIFY,
    Platform.SENSOR,
]

DEFAULT_PORT = 7979
DEFAULT_TIMEOUT = 10
# Without push this is how fast state changes reach Home Assistant. With push it is only a liveness
# heartbeat: a TV that is switched off cannot push that it went away.
SCAN_INTERVAL_SECONDS = 60

MANUFACTURER = "savin.nyc"
MODEL = "PiPup"

# Config entry data keys for the webhooks this integration registers per TV (both minted once and
# kept, so the URLs the TV holds stay valid across Home Assistant restarts).
CONF_PUSH_WEBHOOK_ID = "push_webhook_id"
CONF_CALLBACK_WEBHOOK_ID = "callback_webhook_id"

# Home Assistant event fired when a popup button is pressed on the TV.
EVENT_BUTTON = f"{DOMAIN}_button"
# Home Assistant event fired for the other per-popup callbacks (shown / dismissed).
EVENT_CALLBACK = f"{DOMAIN}_callback"
# Home Assistant event fired for every state change the TV pushes (popup shown/removed, screen on/off…).
EVENT_PUSH = f"{DOMAIN}_event"

# hass.data key -> {token: CallbackToken}; see callbacks.py.
DATA_CALLBACK_TOKENS = f"{DOMAIN}_callback_tokens"

# A callback token outlives its popup by this much (button presses can come a moment after the
# duration ran out), and lasts at least CALLBACK_TOKEN_MIN_TTL. Sticky popups get the long TTL.
CALLBACK_TOKEN_GRACE = timedelta(minutes=5)
CALLBACK_TOKEN_MIN_TTL = timedelta(minutes=15)
CALLBACK_TOKEN_STICKY_TTL = timedelta(days=7)

# Repair issue raised while the TV lacks "display over other apps".
ISSUE_OVERLAY_PERMISSION = "overlay_permission"
OVERLAY_PERMISSION_COMMAND = (
    "adb shell appops set nyc.savin.pipup SYSTEM_ALERT_WINDOW allow"
)

# App versions that introduced features an older app would reject outright. An older app ignores
# unknown JSON keys, so only new position ordinals and new media types need gating: those make the
# app's parser fail the whole /notify.
APP_VERSION_POSITIONS_5_8 = (0, 4, 0)
APP_VERSION_WHEP = (0, 4, 0)
APP_VERSION_PUSH = (0, 4, 0)
APP_VERSION_GRID = (0, 5, 0)

# Camera modes for pipup.send's camera_entity.
CAMERA_MODE_MJPEG = "mjpeg"
CAMERA_MODE_STREAM = "stream"
CAMERA_MODE_SNAPSHOT = "snapshot"
CAMERA_MODES = [CAMERA_MODE_MJPEG, CAMERA_MODE_STREAM, CAMERA_MODE_SNAPSHOT]

# Service field name (Home Assistant) -> PiPup JSON key. Scalar, top-level fields only; media, buttons
# and the per-media options are nested and handled in payload.py.
FIELD_MAP: dict[str, str] = {
    "title": "title",
    "message": "message",
    "id": "id",
    "duration": "duration",
    "position": "position",
    "tts": "tts",
    "tts_language": "ttsLanguage",
    "sound": "sound",
    "sound_volume": "soundVolume",
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
    "opacity": "opacity",
    "dismiss_screensaver": "dismissScreensaver",
    "fullscreen": "fullscreen",
}
