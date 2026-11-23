"""Setting up a TV: push, entities, repair issue, services."""

from __future__ import annotations

from unittest.mock import patch
from urllib.parse import urlparse

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import issue_registry as ir

from pytest_homeassistant_custom_component.common import MockConfigEntry, async_capture_events
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.pipup.camera_media import CameraMedia
from custom_components.pipup.const import (
    CONF_CALLBACK_WEBHOOK_ID,
    CONF_PUSH_WEBHOOK_ID,
    DOMAIN,
    EVENT_BUTTON,
    EVENT_PUSH,
)

from .conftest import BASE, HA_URL, TV_ID, make_status, setup_tv

NOTIFY = "notify.pipup_living_room"


def _calls(mock: AiohttpClientMocker, method: str, path: str) -> list:
    return [c for c in mock.mock_calls if c[0] == method and str(c[1]).split("?")[0] == BASE + path]


async def test_setup_registers_push_with_the_tv(
    ha_with_url: HomeAssistant, config_entry: MockConfigEntry, tv: AiohttpClientMocker
) -> None:
    hass = ha_with_url
    await setup_tv(hass, config_entry)

    push_id = config_entry.data[CONF_PUSH_WEBHOOK_ID]
    assert push_id and config_entry.data[CONF_CALLBACK_WEBHOOK_ID]
    pushes = _calls(tv, "POST", "/push")
    assert len(pushes) == 1
    url = pushes[0][1]
    assert url.query["url"] == f"{HA_URL}/api/webhook/{push_id}"
    assert config_entry.runtime_data.coordinator.push_active

    assert hass.states.get("binary_sensor.pipup_living_room_connectivity").state == "on"
    assert hass.states.get("binary_sensor.pipup_living_room_screen").state == "on"
    assert hass.states.get("binary_sensor.pipup_living_room_popup_on_screen").state == "off"
    assert hass.states.get("binary_sensor.pipup_living_room_overlay_permission").state == "off"
    assert hass.states.get("sensor.pipup_living_room_popups_on_screen").state == "0"


async def test_old_app_is_polled_not_pushed(
    ha_with_url: HomeAssistant, config_entry: MockConfigEntry, tv: AiohttpClientMocker
) -> None:
    tv.clear_requests()
    status = make_status(version="0.3.3")
    del status["push"]
    tv.get(f"{BASE}/status", json=status)
    await setup_tv(ha_with_url, config_entry)
    assert not _calls(tv, "POST", "/push")
    assert not config_entry.runtime_data.coordinator.push_active


async def test_push_updates_state_and_fires_events(
    ha_with_url: HomeAssistant,
    config_entry: MockConfigEntry,
    tv: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    hass = ha_with_url
    await setup_tv(hass, config_entry)
    events = async_capture_events(hass, EVENT_PUSH)
    client = await hass_client_no_auth()
    path = f"/api/webhook/{config_entry.data[CONF_PUSH_WEBHOOK_ID]}"

    body = make_status(
        active=True,
        count=1,
        popups=[{"id": "door", "position": "TopRight", "media": "whep", "duration": 20}],
        event="popup_shown",
        shownId="door",
    )
    resp = await client.post(path, json=body)
    assert resp.status == 200
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.pipup_living_room_popup_on_screen").state == "on"
    assert hass.states.get("sensor.pipup_living_room_popups_on_screen").state == "1"
    assert events[-1].data["event"] == "popup_shown"
    assert events[-1].data["popup_id"] == "door"
    # Push-only keys do not leak into the stored status.
    assert "event" not in config_entry.runtime_data.coordinator.data

    resp = await client.post(
        path, json=make_status(screenOn=False, event="popup_removed", removedId="door", reason="expired")
    )
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.pipup_living_room_screen").state == "off"
    assert events[-1].data == {
        "entry_id": config_entry.entry_id,
        "device_id": events[-1].data["device_id"],
        "event": "popup_removed",
        "popup_id": "door",
        "reason": "expired",
    }
    assert events[-1].data["device_id"]


async def test_push_from_another_tv_is_ignored(
    ha_with_url: HomeAssistant,
    config_entry: MockConfigEntry,
    tv: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    hass = ha_with_url
    await setup_tv(hass, config_entry)
    client = await hass_client_no_auth()
    resp = await client.post(
        f"/api/webhook/{config_entry.data[CONF_PUSH_WEBHOOK_ID]}",
        json=make_status(id="someone-else", count=5),
    )
    assert resp.status == 409
    assert config_entry.runtime_data.coordinator.data["count"] == 0


async def test_overlay_permission_repair_issue(
    ha_with_url: HomeAssistant,
    config_entry: MockConfigEntry,
    tv: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    hass = ha_with_url
    tv.clear_requests()
    tv.get(f"{BASE}/status", json=make_status(overlayPermission=False))
    tv.post(f"{BASE}/push", json={"enabled": True})
    await setup_tv(hass, config_entry)

    issue_id = f"overlay_permission_{config_entry.entry_id}"
    issue = ir.async_get(hass).async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert "SYSTEM_ALERT_WINDOW" in issue.translation_placeholders["command"]
    assert hass.states.get("binary_sensor.pipup_living_room_overlay_permission").state == "on"

    client = await hass_client_no_auth()
    await client.post(
        f"/api/webhook/{config_entry.data[CONF_PUSH_WEBHOOK_ID]}",
        json=make_status(overlayPermission=True, event="started"),
    )
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None


async def test_device_info_follows_the_tv(
    ha_with_url: HomeAssistant, config_entry: MockConfigEntry, tv: AiohttpClientMocker
) -> None:
    hass = ha_with_url
    await setup_tv(hass, config_entry)
    from homeassistant.helpers import device_registry as dr

    [device] = dr.async_entries_for_config_entry(dr.async_get(hass), config_entry.entry_id)
    assert device.sw_version == "0.4.1"
    assert device.hw_version == "SHIELD Android TV"


async def test_send_with_buttons_gets_a_per_popup_callback(
    ha_with_url: HomeAssistant,
    config_entry: MockConfigEntry,
    tv: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    hass = ha_with_url
    await setup_tv(hass, config_entry)
    await hass.services.async_call(
        DOMAIN,
        "send",
        {
            "entity_id": NOTIFY,
            "title": "Door",
            "position": "6",
            "buttons": [{"id": "unlock", "label": "Open"}],
            "duration": 20,
        },
        blocking=True,
    )
    payload = _calls(tv, "POST", "/notify")[-1][2]
    assert payload["position"] == 6
    assert payload["id"].startswith("ha-")
    callback = urlparse(payload["callback"])
    assert f"{callback.scheme}://{callback.netloc}" == HA_URL
    assert callback.path == f"/api/webhook/{config_entry.data[CONF_CALLBACK_WEBHOOK_ID]}"

    # The TV reports the press to that URL; Home Assistant fires pipup_button.
    events = async_capture_events(hass, EVENT_BUTTON)
    client = await hass_client_no_auth()
    resp = await client.post(
        f"{callback.path}?{callback.query}", json={"event": "button", "button": "unlock", "id": "x"}
    )
    assert resp.status == 200
    await hass.async_block_till_done()
    assert events[0].data["button"] == "unlock"
    assert events[0].data["popup_id"] == payload["id"]

    # Without the token: refused.
    resp = await client.post(callback.path, json={"event": "button", "button": "unlock"})
    assert resp.status == 403


async def test_send_refuses_what_an_old_app_would_reject(
    ha_with_url: HomeAssistant, config_entry: MockConfigEntry, tv: AiohttpClientMocker
) -> None:
    hass = ha_with_url
    tv.clear_requests()
    status = make_status(version="0.3.4")
    tv.get(f"{BASE}/status", json=status)
    tv.post(f"{BASE}/push", status=404)
    tv.post(f"{BASE}/notify", json={"status": "ok", "id": "x"})
    await setup_tv(hass, config_entry)
    with pytest.raises(ServiceValidationError, match="0.4.0"):
        await hass.services.async_call(
            DOMAIN, "send", {"entity_id": NOTIFY, "whep_uri": "http://g/api/webrtc?src=a"}, blocking=True
        )
    with pytest.raises(ServiceValidationError, match="at most one"):
        await hass.services.async_call(
            DOMAIN,
            "send",
            {"entity_id": NOTIFY, "image_uri": "http://i", "video_uri": "rtsp://v"},
            blocking=True,
        )
    assert not _calls(tv, "POST", "/notify")


async def test_send_camera_entity_live(
    ha_with_url: HomeAssistant, config_entry: MockConfigEntry, tv: AiohttpClientMocker
) -> None:
    hass = ha_with_url
    await setup_tv(hass, config_entry)
    media = CameraMedia(web_uri="http://ha/stream?authSig=a", poster_uri="http://ha/snap?authSig=b")
    with patch("custom_components.pipup.notify.async_camera_media", return_value=media) as resolve:
        await hass.services.async_call(
            DOMAIN,
            "send",
            {"entity_id": NOTIFY, "camera_entity": "camera.front_door", "duration": 30},
            blocking=True,
        )
    resolve.assert_awaited_once_with(hass, "camera.front_door", "mjpeg", 30)
    payload = _calls(tv, "POST", "/notify")[-1][2]
    assert payload["media"] == {
        "web": {"uri": "http://ha/stream?authSig=a", "muted": True, "poster": "http://ha/snap?authSig=b"}
    }


async def test_send_camera_snapshot_uploads_the_image(
    ha_with_url: HomeAssistant, config_entry: MockConfigEntry, tv: AiohttpClientMocker
) -> None:
    hass = ha_with_url
    await setup_tv(hass, config_entry)
    media = CameraMedia(snapshot=b"\xff\xd8jpeg")
    with patch("custom_components.pipup.notify.async_camera_media", return_value=media):
        await hass.services.async_call(
            DOMAIN,
            "send",
            {
                "entity_id": NOTIFY,
                "camera_entity": "camera.front_door",
                "camera_mode": "snapshot",
                "title": "Door",
                "media_width": 400,
                "buttons": [{"id": "a", "label": "A"}],
            },
            blocking=True,
        )
    call = _calls(tv, "POST", "/notify")[-1]
    body, headers = call[2], call[3]
    assert headers["Content-Type"].startswith("multipart/form-data; boundary=")
    # Text fields carry no Content-Type (the app's server would take them for files); the image does.
    assert b'name="title"\r\n\r\nDoor\r\n' in body
    assert b'name="imageWidth"\r\n\r\n400\r\n' in body
    assert b'filename="snapshot.jpg"\r\nContent-Type: image/jpeg\r\n\r\n\xff\xd8jpeg' in body
    assert b"text/plain" not in body
    # Buttons and callback cannot travel over multipart: dropped.
    assert b'name="buttons"' not in body and b'name="callback"' not in body


async def test_dismiss_and_buttons(
    ha_with_url: HomeAssistant, config_entry: MockConfigEntry, tv: AiohttpClientMocker
) -> None:
    hass = ha_with_url
    await setup_tv(hass, config_entry)
    await hass.services.async_call(DOMAIN, "dismiss", {"entity_id": NOTIFY, "id": "door"}, blocking=True)
    assert str(_calls(tv, "POST", "/cancel")[-1][1]).endswith("/cancel?id=door")
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.pipup_living_room_dismiss_popups"}, blocking=True
    )
    assert str(_calls(tv, "POST", "/cancel")[-1][1]) == f"{BASE}/cancel"
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.pipup_living_room_wake_screen"}, blocking=True
    )
    assert _calls(tv, "POST", "/power")


async def test_unload_and_remove(
    ha_with_url: HomeAssistant, config_entry: MockConfigEntry, tv: AiohttpClientMocker
) -> None:
    hass = ha_with_url
    await setup_tv(hass, config_entry)
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    last_push = _calls(tv, "POST", "/push")[-1][1]
    assert last_push.query["url"] == ""


async def test_diagnostics_redact_secrets(
    ha_with_url: HomeAssistant, config_entry: MockConfigEntry, tv: AiohttpClientMocker
) -> None:
    hass = ha_with_url
    await setup_tv(hass, config_entry)
    from custom_components.pipup.diagnostics import async_get_config_entry_diagnostics

    diag = await async_get_config_entry_diagnostics(hass, config_entry)
    assert diag["entry"]["data"][CONF_PUSH_WEBHOOK_ID] == "**REDACTED**"
    assert diag["status"]["id"] == TV_ID
