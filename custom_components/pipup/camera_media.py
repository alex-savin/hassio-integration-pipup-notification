"""Resolve a Home Assistant camera entity into media a PiPup popup can show.

The TV gets URLs on Home Assistant itself (its camera proxy, or an HLS stream), so it never needs the
camera's own address or credentials; a snapshot is uploaded to the TV directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import CAMERA_MODE_MJPEG, CAMERA_MODE_SNAPSHOT

# The poster is fetched once, when the popup opens.
POSTER_SIGNATURE = timedelta(hours=1)
# A live MJPEG popup keeps its URL open while it is on screen; a sticky one may stay for days.
MJPEG_SIGNATURE = timedelta(hours=24)
MJPEG_SIGNATURE_STICKY = timedelta(days=30)


@dataclass
class CameraMedia:
    """What to put in the popup for a camera: exactly one of the three, plus an optional poster."""

    web_uri: str | None = None
    video_uri: str | None = None
    snapshot: bytes | None = None
    snapshot_type: str = "image/jpeg"
    poster_uri: str | None = None


def _base_url(hass: HomeAssistant) -> str:
    # The TV is on the LAN: hand it Home Assistant's internal address.
    try:
        return get_url(hass, allow_external=False, prefer_external=False)
    except NoURLAvailableError as err:
        raise HomeAssistantError(
            "Home Assistant has no internal URL the TV could use; set one under "
            "Settings > System > Network"
        ) from err


def _signed(hass: HomeAssistant, path: str, lifetime: timedelta) -> str:
    # Imported here so the http component is only needed when cameras are used.
    from homeassistant.components.http.auth import async_sign_path  # noqa: PLC0415

    # Sign as Home Assistant's content user, not as whoever called the service: a URL signed with an
    # admin's refresh token dies when that session is revoked.
    return async_sign_path(hass, path, lifetime, use_content_user=True)


async def async_camera_media(
    hass: HomeAssistant, entity_id: str, mode: str, duration: int | None
) -> CameraMedia:
    """Build the media for ``entity_id`` in ``mode`` (mjpeg, stream or snapshot)."""
    from homeassistant.components import camera  # noqa: PLC0415

    if mode == CAMERA_MODE_SNAPSHOT:
        image = await camera.async_get_image(hass, entity_id)
        return CameraMedia(snapshot=image.content, snapshot_type=image.content_type)

    base = _base_url(hass)
    poster = base + _signed(hass, f"/api/camera_proxy/{entity_id}", POSTER_SIGNATURE)

    if mode == CAMERA_MODE_MJPEG:
        # Only an explicit, finite duration gets the short signature; a sticky popup (or one whose
        # duration we do not know) must not go dark after a day.
        lifetime = (
            MJPEG_SIGNATURE if duration is not None and duration > 0 else MJPEG_SIGNATURE_STICKY
        )
        stream = base + _signed(hass, f"/api/camera_proxy_stream/{entity_id}", lifetime)
        return CameraMedia(web_uri=stream, poster_uri=poster)

    # HLS through Home Assistant's stream integration; the path carries its own access token.
    path = await camera.async_request_stream(hass, entity_id, "hls")
    return CameraMedia(video_uri=base + path, poster_uri=poster)
