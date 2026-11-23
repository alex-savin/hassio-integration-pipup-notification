"""Shared fixtures for the PiPup tests."""

from __future__ import annotations

from typing import Any

import pytest

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.setup import async_setup_component

from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.pipup.const import DOMAIN

HOST = "10.0.0.50"
PORT = 7979
BASE = f"http://{HOST}:{PORT}"
TV_ID = "aabf63c8-4de6-3d28-92bb-3ed64d517fa3"
HA_URL = "http://10.0.0.2:8123"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load custom_components/ in every test."""


def make_status(**overrides: Any) -> dict[str, Any]:
    """A /status answer from a 0.4.x app."""
    status: dict[str, Any] = {
        "app": "nyc.savin.pipup",
        "version": "0.4.1",
        "id": TV_ID,
        "name": "Living Room",
        "port": PORT,
        "active": False,
        "count": 0,
        "screenOn": True,
        "dreaming": False,
        "uptimeSeconds": 10,
        "authEnabled": False,
        "overlayPermission": True,
        "push": {"enabled": False, "lastEvent": None, "lastStatus": None, "lastAt": None, "dropped": 0},
        "popups": [],
        "lastPopup": None,
        "device": {"manufacturer": "NVIDIA", "model": "SHIELD Android TV", "android": "11", "sdk": 30},
    }
    status.update(overrides)
    return status


@pytest.fixture
async def ha_with_url(hass: HomeAssistant) -> HomeAssistant:
    """Home Assistant with an internal URL (the TV needs one to reach it) and http/webhook loaded."""
    await async_process_ha_core_config(hass, {"internal_url": HA_URL})
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, "webhook", {})
    return hass


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """A configured TV."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="PiPup Living Room",
        unique_id=TV_ID,
        data={CONF_HOST: HOST, CONF_PORT: PORT, CONF_TOKEN: None},
    )


@pytest.fixture
def tv(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """The TV's HTTP API with sensible defaults; tests override answers as needed."""
    aioclient_mock.get(f"{BASE}/status", json=make_status())
    aioclient_mock.post(f"{BASE}/push", json={"enabled": True})
    aioclient_mock.post(f"{BASE}/notify", json={"status": "ok", "id": "x"})
    aioclient_mock.post(f"{BASE}/cancel", text="ok")
    aioclient_mock.post(f"{BASE}/power", json={"status": "ok", "reached": True, "screenOn": True})
    return aioclient_mock


async def setup_tv(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Add and set up the entry."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
