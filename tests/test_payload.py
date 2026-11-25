"""Service data -> /notify JSON, and the app-version gates."""

from __future__ import annotations

import pytest

from custom_components.pipup.payload import (
    UnsupportedByApp,
    build_payload,
    check_supported,
    parse_version,
)


def test_scalar_fields_map_to_app_keys() -> None:
    payload = build_payload(
        {
            "title": "Door",
            "position": 6,
            "opacity": 0.8,
            "sound": "default",
            "sound_volume": 0.3,
            "tts": "Hi",
            "tts_language": "nl-NL",
            "dismiss_screensaver": False,
            "fullscreen": True,
            "not_a_field": 1,
        }
    )
    assert payload == {
        "title": "Door",
        "position": 6,
        "opacity": 0.8,
        "sound": "default",
        "soundVolume": 0.3,
        "tts": "Hi",
        "ttsLanguage": "nl-NL",
        "dismissScreensaver": False,
        "fullscreen": True,
    }


def test_video_takes_only_video_options() -> None:
    payload = build_payload(
        {
            "video_uri": "rtsp://cam/1",
            "media_width": 640,
            "media_height": 360,  # not a video option
            "muted": True,
            "poster_uri": "http://ha/snap.jpg",
            "poster_mode": "fit",
            "buffer_ms": 300,
            "decoder": "software",
        }
    )
    assert payload["media"] == {
        "video": {
            "uri": "rtsp://cam/1",
            "width": 640,
            "muted": True,
            "poster": "http://ha/snap.jpg",
            "posterMode": "fit",
            "bufferMs": 300,
            "decoder": "software",
        }
    }


def test_web_height_is_an_alias_for_media_height() -> None:
    payload = build_payload({"web_uri": "http://x", "web_height": 300})
    assert payload["media"] == {"web": {"uri": "http://x", "height": 300}}
    # The new name wins when both are given.
    payload = build_payload({"web_uri": "http://x", "web_height": 300, "media_height": 400})
    assert payload["media"]["web"]["height"] == 400


def test_whep_and_image() -> None:
    assert build_payload({"whep_uri": "http://g/api/webrtc?src=a", "media_height": 270})["media"] == {
        "whep": {"uri": "http://g/api/webrtc?src=a", "height": 270}
    }
    # An image takes neither poster nor muted.
    assert build_payload({"image_uri": "http://i", "poster_uri": "p", "muted": True})["media"] == {
        "image": {"uri": "http://i"}
    }


def test_grid_accepts_urls_and_tiles() -> None:
    payload = build_payload(
        {
            "grid": [
                "http://g/api/webrtc?src=a",
                {"uri": "http://g/api/webrtc?src=b", "label": "Back", "poster": "http://p/b"},
                {"whep_uri": "http://g/api/webrtc?src=c", "poster_uri": "http://p/c"},
            ],
            "grid_columns": 3,
            "grid_labels": False,
            "muted": True,
        }
    )
    assert payload["media"] == {
        "grid": {
            "items": [
                {"uri": "http://g/api/webrtc?src=a"},
                {"uri": "http://g/api/webrtc?src=b", "label": "Back", "poster": "http://p/b"},
                {"uri": "http://g/api/webrtc?src=c", "poster": "http://p/c"},
            ],
            "columns": 3,
            "labels": False,
            "muted": True,
        }
    }


def test_buttons_pass_through() -> None:
    buttons = [{"id": "ok", "label": "OK"}]
    assert build_payload({"buttons": buttons})["buttons"] == buttons


@pytest.mark.parametrize(
    ("version", "expected"),
    [("0.4.1", (0, 4, 1)), ("1.0.0-beta.1", (1, 0, 0)), (None, None), ("dev", None), (3, None)],
)
def test_parse_version(version, expected) -> None:
    assert parse_version(version) == expected


@pytest.mark.parametrize(
    ("payload", "version", "allowed"),
    [
        ({"position": 4}, "0.3.3", True),
        ({"position": 5}, "0.3.4", False),
        ({"position": 8}, "0.4.0", True),
        ({"media": {"whep": {"uri": "u"}}}, "0.3.4", False),
        ({"media": {"whep": {"uri": "u"}}}, "0.4.0", True),
        ({"media": {"grid": {"items": []}}}, "0.4.1", False),
        ({"media": {"grid": {"items": []}}}, "0.5.0", True),
        # Unknown keys are ignored by older apps, so they are never gated.
        ({"fullscreen": True, "opacity": 0.5}, "0.3.0", True),
        # An unknown version (TV not reached yet) is not gated.
        ({"position": 8, "media": {"grid": {}}}, None, True),
    ],
)
def test_check_supported(payload, version, allowed) -> None:
    if allowed:
        check_supported(payload, version)
    else:
        with pytest.raises(UnsupportedByApp):
            check_supported(payload, version)
