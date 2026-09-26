"""Portable display preferences, excluding credentials and cloud policy."""

from copy import deepcopy
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

RANGES = {
    **dict.fromkeys(
        (
            "dark_mode",
            "fahrenheit",
            "time_24h",
            "auto_brightness",
            "quiet_hours",
            "ui_sounds",
            "notification_sounds",
        ),
        (0, 1),
    ),
    "display_brightness": (10, 255),
    "ring_brightness": (0, 64),
    "volume": (0, 10),
    "quiet_start": (0, 1439),
    "quiet_end": (0, 1439),
    "quiet_display": (1, 255),
    "quiet_ring": (0, 64),
    "quiet_volume": (0, 10),
    "voc_mode": (0, 2),
    "locale": (0, 1),
    "index_mode": (0, 1),
}


def validate_profile(profile: Any) -> dict[str, Any]:
    """Validate a complete preference profile before sending it to the device."""
    if (
        not isinstance(profile, dict)
        or set(profile) != {"schema", "settings"}
        or type(profile["schema"]) is not int
        or profile["schema"] != 1
    ):
        raise ValueError("Unsupported preferences profile")
    values = profile["settings"]
    if not isinstance(values, dict) or set(values) != {*RANGES, "timezone"}:
        raise ValueError("Profile must contain the complete display settings")
    for key, (low, high) in RANGES.items():
        if type(values[key]) is not int or not low <= values[key] <= high:
            raise ValueError("Invalid preference value")
    if (
        not isinstance(values["timezone"], str)
        or not 1 <= len(values["timezone"]) <= 63
    ):
        raise ValueError("Invalid timezone")
    try:
        ZoneInfo(values["timezone"])
    except (ZoneInfoNotFoundError, ValueError) as err:
        raise ValueError("Invalid timezone") from err
    return deepcopy(profile)


def export_profile(settings: dict[str, Any]) -> dict[str, Any]:
    """Explicit allowlist prevents future fields from leaking into backups."""
    try:
        return validate_profile(
            {
                "schema": 1,
                "settings": {key: settings[key] for key in (*RANGES, "timezone")},
            }
        )
    except KeyError as err:
        raise ValueError(
            "Device does not provide a complete preferences profile"
        ) from err
