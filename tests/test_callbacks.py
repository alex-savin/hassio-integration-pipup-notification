"""Per-popup callback tokens."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory

from homeassistant.core import HomeAssistant

from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.pipup.callbacks import handle_callback, issue_token, token_ttl
from custom_components.pipup.const import EVENT_BUTTON, EVENT_CALLBACK


def _issue(hass: HomeAssistant, entry_id: str = "entry1", duration: int | None = 20) -> str:
    return issue_token(
        hass,
        entry_id=entry_id,
        device_id="dev1",
        popup_id="door",
        buttons=[{"id": "unlock", "label": "Open"}, {"id": "ignore", "label": "Dismiss"}],
        duration=duration,
    )


def test_ttl() -> None:
    assert token_ttl(20) == timedelta(minutes=15)  # at least 15 minutes
    assert token_ttl(3600) == timedelta(minutes=65)  # duration + 5 minutes
    assert token_ttl(None) == timedelta(minutes=15)  # the app's default 30 s
    assert token_ttl(0) == timedelta(days=7)  # sticky
    assert token_ttl(-1) == timedelta(days=7)


async def test_button_event_comes_from_the_record(hass: HomeAssistant) -> None:
    events = async_capture_events(hass, EVENT_BUTTON)
    token = _issue(hass)
    # The body claims another popup and label; the event must use what Home Assistant issued.
    assert handle_callback(
        hass, "entry1", token, {"event": "button", "id": "garage", "button": "unlock", "label": "x"}
    )
    await hass.async_block_till_done()
    assert [e.data for e in events] == [
        {"entry_id": "entry1", "device_id": "dev1", "popup_id": "door", "button": "unlock", "label": "Open"}
    ]


async def test_one_press_per_popup(hass: HomeAssistant) -> None:
    token = _issue(hass)
    assert handle_callback(hass, "entry1", token, {"event": "button", "button": "unlock"})
    assert not handle_callback(hass, "entry1", token, {"event": "button", "button": "ignore"})


async def test_rejects_unknown_button_token_and_entry(hass: HomeAssistant) -> None:
    token = _issue(hass)
    assert not handle_callback(hass, "entry1", token, {"event": "button", "button": "garage"})
    assert not handle_callback(hass, "entry1", "forged", {"event": "button", "button": "unlock"})
    assert not handle_callback(hass, "entry1", None, {"event": "button", "button": "unlock"})
    # A token presented on another TV's webhook is rejected and burnt.
    assert not handle_callback(hass, "entry2", token, {"event": "button", "button": "unlock"})
    assert not handle_callback(hass, "entry1", token, {"event": "button", "button": "unlock"})


async def test_lifecycle_and_dismissed_ends_the_token(hass: HomeAssistant) -> None:
    events = async_capture_events(hass, EVENT_CALLBACK)
    token = _issue(hass)
    assert handle_callback(hass, "entry1", token, {"event": "shown", "id": "door"})
    assert handle_callback(hass, "entry1", token, {"event": "button", "button": "ignore"})
    assert handle_callback(hass, "entry1", token, {"event": "dismissed", "id": "door"})
    assert not handle_callback(hass, "entry1", token, {"event": "shown"})
    await hass.async_block_till_done()
    assert [e.data["event"] for e in events] == ["shown", "dismissed"]


async def test_expired_token_is_rejected(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    token = _issue(hass, duration=20)
    freezer.tick(timedelta(minutes=16))
    assert not handle_callback(hass, "entry1", token, {"event": "button", "button": "unlock"})
