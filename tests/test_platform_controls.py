"""Exercise each exposed device control and translated errors."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.terrestream_local import async_remove_entry, async_unload_entry
from custom_components.terrestream_local.button import Button
from custom_components.terrestream_local.coordinator import Coordinator
from custom_components.terrestream_local.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.terrestream_local.number import Number
from custom_components.terrestream_local.select import Select
from custom_components.terrestream_local.switch import Switch
from custom_components.terrestream_local.text import Text
from custom_components.terrestream_local.update import Update
from terrestream_local.errors import (
    AuthenticationError,
    ClientError,
    ControllerConflict,
)

from .test_client import TOKEN, snapshot
from .test_integration import config_entry


async def test_controls_preserve_values_and_reject_invalid_requests(hass):
    entry = config_entry()
    entry.add_to_hass(hass)
    coordinator = Coordinator(hass, entry, AsyncMock())
    coordinator.data = snapshot()
    coordinator.data["settings"].update(
        volume=5, quiet_start=1320, timezone="America/New_York", locale=0
    )
    coordinator.command = AsyncMock()
    number = Number(coordinator, "volume", "Volume", 0, 10)
    assert number.native_value == 5
    await number.async_set_native_value(7)
    coordinator.command.assert_awaited_with("set", key="volume", value=7)
    with pytest.raises(HomeAssistantError):
        await number.async_set_native_value(2.5)
    text = Text(coordinator, "quiet_start", "Start", True)
    assert text.native_value == "22:00"
    await text.async_set_value("06:15")
    coordinator.command.assert_awaited_with("set", key="quiet_start", value=375)
    with pytest.raises(HomeAssistantError):
        await text.async_set_value("24:30")
    zone = Text(coordinator, "timezone", "Zone", True)
    assert zone.native_value == "America/New_York"
    await zone.async_set_value("Europe/Paris")
    select = Select(coordinator, "locale", "Language", ["English", "Français"])
    assert select.current_option == "English"
    await select.async_select_option("Français")
    switch = Switch(coordinator, "dark_mode", "Dark", True)
    await switch.async_turn_off()
    await Button(coordinator, "fan_clean", "Clean", True).async_press()
    update = Update(coordinator, "firmware_update", "Firmware", True)
    coordinator.data["update"]["latest_version"] = "4.1.1"
    await update.async_install("4.1.1", False)
    with pytest.raises(HomeAssistantError):
        await update.async_install("9.9.9", False)
    coordinator.data["update_operation"] = {
        "method": "install_update",
        "status": "awaiting_validation",
        "target_version": "4.1.1",
    }
    assert update.in_progress
    assert update.extra_state_attributes["update_status"] == "awaiting_validation"


@pytest.mark.parametrize(
    "error,expected",
    [
        (AuthenticationError("revoked"), ConfigEntryAuthFailed),
        (ControllerConflict("clone"), UpdateFailed),
        (ClientError("offline"), UpdateFailed),
    ],
)
async def test_coordinator_errors_and_action_failure(hass, error, expected):
    entry = config_entry()
    entry.add_to_hass(hass)
    client = AsyncMock()
    client.refresh.side_effect = error
    coordinator = Coordinator(hass, entry, client)
    with pytest.raises(expected):
        await coordinator._async_update_data()
    client.command.side_effect = error
    with pytest.raises(HomeAssistantError):
        await coordinator.command("set", key="dark_mode", value=1)


async def test_unload_failure_and_successful_removal(hass):
    entry = config_entry()
    entry.add_to_hass(hass)
    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=False
    ):
        assert not await async_unload_entry(hass, entry)
    with patch("custom_components.terrestream_local.Client", autospec=True) as factory:
        await async_remove_entry(hass, entry)
        factory.return_value.command.assert_awaited_once_with("unpair")


async def test_diagnostics_rejects_malformed_and_secret_labels(hass):
    entry = config_entry()
    data = snapshot()
    data["model"] = "bad\nlabel"
    data["hardware"] = entry.data["host"]
    entry.runtime_data = SimpleNamespace(data=data, last_update_success=True)
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["model"] == "unknown"
    assert result["hardware"] in {"unknown", "redacted"}


@pytest.mark.parametrize(
    "error,expected",
    [
        (AuthenticationError("revoked"), ConfigEntryAuthFailed),
        (ClientError("offline"), ConfigEntryNotReady),
    ],
)
async def test_setup_identity_failure_is_recoverable(hass, error, expected):
    from custom_components.terrestream_local import async_setup_entry

    entry = config_entry()
    entry.add_to_hass(hass)
    with patch("custom_components.terrestream_local.Client", autospec=True) as factory:
        factory.return_value.identity.side_effect = error
        with pytest.raises(expected):
            await async_setup_entry(hass, entry)


async def test_unload_succeeds_when_device_cannot_receive_release(hass):
    entry = config_entry()
    entry.add_to_hass(hass)
    client = AsyncMock()
    client.command.side_effect = ClientError("offline")
    entry.runtime_data = SimpleNamespace(async_shutdown=AsyncMock(), client=client)
    with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
        assert await async_unload_entry(hass, entry)
    entry.runtime_data.async_shutdown.assert_awaited_once()


async def test_diagnostics_only_reports_bounded_health_and_update_outcomes(hass):
    entry = config_entry()
    data = snapshot()
    data["health"] = {
        "preferences_storage_ok": True,
        "local_stack_boot_ready": True,
        "update_health_proven": True,
        "reset_reason": 11,
        "internal_heap_free": 45000,
    }
    data["update_operation"] = {"status": "rolled_back", "target_version": TOKEN}
    entry.runtime_data = SimpleNamespace(data=data, last_update_success=True)
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["reset_reason"] == 11
    assert result["local_stack_boot_ready"] is True
    assert result["update_status"] == "rolled_back"
    assert result["preferences_storage_ok"] and result["update_health_proven"]
    assert TOKEN not in str(result)
    data["health"]["reset_reason"] = 99
    data["update_operation"]["status"] = TOKEN
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["reset_reason"] is None
    assert result["update_status"] == "unknown"


async def test_commands_serialize_immediate_readback(hass):
    import asyncio

    entry = config_entry()
    entry.add_to_hass(hass)
    client = AsyncMock()
    coordinator = Coordinator(hass, entry, client)
    stages = []

    async def command(method, **arguments):
        stages.append(("command", arguments["value"]))
        await asyncio.sleep(0)

    async def refresh():
        stages.append(("readback", None))
        await asyncio.sleep(0)

    client.command.side_effect = command
    coordinator.async_refresh = AsyncMock(side_effect=refresh)
    coordinator.async_request_refresh = AsyncMock()
    await asyncio.gather(
        coordinator.command("set", key="dark_mode", value=1),
        coordinator.command("set", key="dark_mode", value=0),
    )
    assert stages == [
        ("command", 1),
        ("readback", None),
        ("command", 0),
        ("readback", None),
    ]
    coordinator.async_request_refresh.assert_not_awaited()
