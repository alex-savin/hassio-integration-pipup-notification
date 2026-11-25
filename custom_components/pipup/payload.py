"""Turn ``pipup.send`` service data into the app's ``/notify`` JSON, and gate it on the app version.

Kept free of Home Assistant state so it is unit-testable on its own.
"""

from __future__ import annotations

import re
from typing import Any

from .const import (
    APP_VERSION_GRID,
    APP_VERSION_POSITIONS_5_8,
    APP_VERSION_WHEP,
    FIELD_MAP,
)

# Per-media options -> JSON key inside the media object, and which media types take them.
_MEDIA_OPTIONS: dict[str, tuple[str, frozenset[str]]] = {
    "media_width": ("width", frozenset({"image", "video", "web", "whep", "grid"})),
    "media_height": ("height", frozenset({"web", "whep", "grid"})),
    "muted": ("muted", frozenset({"video", "web", "whep", "grid"})),
    "poster_uri": ("poster", frozenset({"video", "web", "whep"})),
    "poster_mode": ("posterMode", frozenset({"video", "web", "whep"})),
    "buffer_ms": ("bufferMs", frozenset({"video"})),
    "decoder": ("decoder", frozenset({"video"})),
    "grid_columns": ("columns", frozenset({"grid"})),
    "grid_labels": ("labels", frozenset({"grid"})),
}

# The service field that selects each media type, in the order they are tried.
_MEDIA_SOURCES: tuple[tuple[str, str], ...] = (
    ("image_uri", "image"),
    ("video_uri", "video"),
    ("web_uri", "web"),
    ("whep_uri", "whep"),
    ("grid", "grid"),
)

_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


class UnsupportedByApp(ValueError):
    """The popup uses something the app on the TV is too old to accept."""


def parse_version(version: Any) -> tuple[int, int, int] | None:
    """``"0.4.1"`` -> ``(0, 4, 1)``; ``None`` when unknown. Suffixes such as ``-rc1`` are ignored."""
    if not isinstance(version, str) or not (match := _VERSION_RE.match(version)):
        return None
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


def media_type(data: dict[str, Any]) -> str | None:
    """The media type the service data asks for (first match wins), or None for a text popup."""
    for field, kind in _MEDIA_SOURCES:
        if data.get(field):
            return kind
    return None


def _grid_items(tiles: list[Any]) -> list[dict[str, Any]]:
    items = []
    for tile in tiles:
        if isinstance(tile, str):
            items.append({"uri": tile})
            continue
        item: dict[str, Any] = {"uri": tile.get("uri") or tile.get("whep_uri") or tile.get("url")}
        if label := tile.get("label"):
            item["label"] = label
        if poster := tile.get("poster") or tile.get("poster_uri"):
            item["poster"] = poster
        items.append(item)
    return items


def build_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Map Home Assistant service fields onto the PiPup ``/notify`` JSON body."""
    # "web_height" predates media_height and still works for web pages.
    if "web_height" in data and "media_height" not in data:
        data = {**data, "media_height": data["web_height"]}

    payload: dict[str, Any] = {
        FIELD_MAP[key]: value for key, value in data.items() if key in FIELD_MAP
    }
    if (buttons := data.get("buttons")) is not None:
        payload["buttons"] = buttons

    kind = media_type(data)
    if kind is None:
        return payload

    media: dict[str, Any]
    if kind == "grid":
        media = {"items": _grid_items(data["grid"])}
    else:
        media = {"uri": data[f"{kind}_uri"]}
    for field, (key, kinds) in _MEDIA_OPTIONS.items():
        if kind in kinds and data.get(field) is not None:
            media[key] = data[field]
    payload["media"] = {kind: media}
    return payload


def check_supported(payload: dict[str, Any], version: Any) -> None:
    """Raise :class:`UnsupportedByApp` if an app at ``version`` would reject ``payload``.

    Only position ordinals and media types are checked: an older app ignores unknown keys, but an
    unknown position or media type makes it fail the whole notification. An unknown version (the TV
    has not answered yet) is not gated; the app's own error then applies.
    """
    parsed = parse_version(version)
    if parsed is None:
        return
    position = payload.get("position")
    if isinstance(position, int) and position >= 5 and parsed < APP_VERSION_POSITIONS_5_8:
        raise UnsupportedByApp(
            f"position {position} needs PiPup {_fmt(APP_VERSION_POSITIONS_5_8)} or newer (the TV runs {version})"
        )
    media = payload.get("media") or {}
    needs = {"whep": APP_VERSION_WHEP, "grid": APP_VERSION_GRID}
    for kind, minimum in needs.items():
        if kind in media and parsed < minimum:
            raise UnsupportedByApp(
                f"{kind} media needs PiPup {_fmt(minimum)} or newer (the TV runs {version})"
            )


def _fmt(version: tuple[int, int, int]) -> str:
    return ".".join(str(part) for part in version)
