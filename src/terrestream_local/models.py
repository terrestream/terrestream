"""Validated snapshot contract shared by the client and its consumers."""

from typing import Any, NotRequired, TypedDict


class Measurement(TypedDict):
    available: bool
    status: str
    value: NotRequired[float | int | None]
    age_ms: NotRequired[int]
    expires_in_ms: NotRequired[int]


class Snapshot(TypedDict):
    protocol: int
    uuid: str
    session: str
    boot: str
    uptime_ms: int
    model: str
    firmware: str
    hardware: NotRequired[str]
    settings_revision: int
    settings: dict[str, int | str]
    capabilities: dict[str, Any]
    measurements: dict[str, Measurement]
    update: dict[str, Any]
    maintenance: dict[str, Any]
    update_operation: NotRequired[dict[str, Any]]
    health: NotRequired[dict[str, Any]]
    local_only_supported: NotRequired[bool]
    cloud_policy: NotRequired[str]
