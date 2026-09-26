"""Allowlisted diagnostics; no addresses, UUIDs, tokens, certs or readings."""

import re
from typing import Any

from homeassistant.core import HomeAssistant

from .sensor import SENSORS
from .types import TerrestreamConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TerrestreamConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    data = coordinator.data or {}
    sensitive = {entry.data.get("host", "")}
    sensitive.update(str(value) for value in entry.data.get("credentials", {}).values())

    def label(value: object) -> str:
        if not isinstance(value, str) or not re.fullmatch(
            r"[A-Za-z0-9 ._+-]{1,48}", value
        ):
            return "unknown"
        if any(secret and secret in value for secret in sensitive if len(secret) > 4):
            return "redacted"
        return value

    status = data.get("maintenance", {}).get("status")
    return {
        "protocol": data.get("protocol"),
        "model": label(data.get("model")),
        "firmware": label(data.get("firmware")),
        "hardware": label(data.get("hardware")),
        "last_update_success": coordinator.last_update_success,
        "uptime_ms": data.get("uptime_ms")
        if type(data.get("uptime_ms")) is int and data["uptime_ms"] >= 0
        else None,
        "memory_sampling_active": data.get("health", {}).get("memory_sampling_active")
        if type(data.get("health", {}).get("memory_sampling_active")) is bool
        else None,
        "measurement_status": {
            key: (
                value.get("status")
                if value.get("status")
                in {"valid", "warming_up", "stale", "cleaning", "sensor_error"}
                else "unknown"
            )
            for key, value in data.get("measurements", {}).items()
            if key in SENSORS
        },
        "update_checked": data.get("update", {}).get("checked"),
        "maintenance_status": status
        if status
        in {"idle", "accepted", "running", "succeeded", "failed", "failed_or_no_update"}
        else "unknown",
        "preferences_storage_ok": data.get("health", {}).get("preferences_storage_ok")
        if type(data.get("health", {}).get("preferences_storage_ok")) is bool
        else None,
        "update_health_proven": data.get("health", {}).get("update_health_proven")
        if type(data.get("health", {}).get("update_health_proven")) is bool
        else None,
        "local_stack_boot_ready": data.get("health", {}).get("local_stack_boot_ready")
        if type(data.get("health", {}).get("local_stack_boot_ready")) is bool
        else None,
        "reset_reason": (
            data.get("health", {}).get("reset_reason")
            if type(data.get("health", {}).get("reset_reason")) is int
            and 0 <= data["health"]["reset_reason"] <= 32
            else None
        ),
        "update_status": data.get("update_operation", {}).get("status")
        if data.get("update_operation", {}).get("status")
        in {
            "idle",
            "accepted",
            "awaiting_validation",
            "succeeded",
            "rolled_back",
            "interrupted",
        }
        else "unknown",
        "resource_health": {
            key: value
            for key, value in data.get("health", {}).items()
            if key
            in {
                "internal_heap_free",
                "internal_heap_min_since_boot",
                "internal_largest_block",
                "internal_sampled_free_min",
                "internal_sampled_largest_min",
                "memory_sample_interval_ms",
            }
            and type(value) is int
            and 0 <= value <= 16 * 1024 * 1024
        },
    }
