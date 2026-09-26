"""Failure recovery at service, registry and stale-sample boundaries."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.terrestream_local.coordinator import Coordinator
from custom_components.terrestream_local.migration import migrate
from custom_components.terrestream_local.services import register
from terrestream_local import Credentials
from terrestream_local.errors import ClientError

from .test_client import TOKEN, UUID, snapshot
from .test_integration import config_entry


@pytest.mark.parametrize(
    "reason,key",
    [
        ("busy", "busy"),
        ("revision_conflict", "revision_conflict"),
        ("storage_failure", "storage_failure"),
        ("invalid_value", "invalid_value"),
        ("unsupported_setting", "unsupported_setting"),
        ("unsupported_method", "unsupported_method"),
        ("secret response", "command_failed"),
    ],
)
async def test_action_failure_is_translated_and_allowlisted(hass, reason, key):
    entry = config_entry()
    entry.add_to_hass(hass)
    client = AsyncMock()
    client.command.side_effect = ClientError(reason)
    with pytest.raises(HomeAssistantError) as failure:
        await Coordinator(hass, entry, client).command("fan_clean")
    assert failure.value.translation_key == key


async def test_accepted_update_does_not_poll_during_restart(hass):
    entry = config_entry()
    entry.add_to_hass(hass)
    coordinator = Coordinator(hass, entry, AsyncMock())
    with patch.object(
        coordinator, "async_request_refresh", new_callable=AsyncMock
    ) as refresh:
        await coordinator.command("install_update")
        refresh.assert_not_awaited()


@pytest.mark.parametrize(
    "profile_supported,available,settings,error",
    [
        (False, True, {}, "profile_unsupported"),
        (True, False, {}, "profile_unavailable"),
        (True, True, {}, "profile_invalid"),
    ],
)
async def test_profile_export_cannot_return_incomplete_or_stale_data(
    hass, profile_supported, available, settings, error
):
    entry = config_entry()
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    entry.runtime_data = SimpleNamespace(
        data={
            "capabilities": {"preferences_profile": int(profile_supported)},
            "settings": settings,
        },
        async_request_refresh=AsyncMock(),
        last_update_success=available,
    )
    register(hass)
    with pytest.raises(HomeAssistantError) as failure:
        await hass.services.async_call(
            "terrestream_local",
            "export_preferences",
            {"config_entry_id": entry.entry_id},
            blocking=True,
            return_response=True,
        )
    assert failure.value.translation_key == error


async def test_sensor_expires_without_waiting_for_next_poll_and_unloads(
    hass, enable_custom_integrations
):
    entry = config_entry()
    entry.add_to_hass(hass)
    with patch("custom_components.terrestream_local.Client", autospec=True) as factory:
        client = factory.return_value
        client.credentials = Credentials(UUID, "ab" * 32, TOKEN)
        client.identity.return_value = {"paired": True}
        client.refresh.return_value = snapshot()
        client.measurement_remaining.side_effect = lambda key: (
            1.0 if key == "co2" else 0.0
        )
        client.measurement_available.side_effect = lambda key: key == "co2"
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get("sensor.terrestream_r500_carbon_dioxide").state == "500"
        client.measurement_available.return_value = False
        client.measurement_available.side_effect = None
        client.measurement_remaining.side_effect = None
        client.measurement_remaining.return_value = 0.0
        async_fire_time_changed(
            hass, datetime.now(UTC) + timedelta(seconds=2), fire_all=True
        )
        await hass.async_block_till_done()
        assert (
            hass.states.get("sensor.terrestream_r500_carbon_dioxide").state
            == "unavailable"
        )
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


def old_measurement(hass, source="mqtt"):
    old = MockConfigEntry(domain=source)
    old.add_to_hass(hass)
    local = config_entry()
    local.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        local, data={**local.data, "legacy_source": source}
    )
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=old.entry_id, identifiers={(source, UUID)}
    )
    entity = er.async_get(hass).async_get_or_create(
        "sensor",
        source,
        f"{UUID}_co2" if source == "mqtt" else "terrestream_42_co2_ppm",
        config_entry=old,
        device_id=device.id,
        unit_of_measurement="ppm",
        capabilities={"state_class": "measurement"},
    )
    return old, local, device, entity


async def test_cloud_migration_ignores_stale_rosters_and_matches_only_uuid(hass):
    old, local, device, entity = old_measurement(hass, "terrestream")
    hass.data["terrestream"] = {
        "stale": SimpleNamespace(last_update_success=False),
        "active_raw": SimpleNamespace(
            last_update_success=True, disable_raw_signals=False
        ),
        old.entry_id: SimpleNamespace(
            last_update_success=True,
            disable_raw_signals=True,
            data={
                "devices": {
                    1: {"meta": {"device_uuid": "other"}},
                    42: {"meta": {"device_uuid": UUID}},
                }
            },
        ),
    }
    area = ar.async_get(hass).async_create("Bedroom")
    dr.async_get(hass).async_update_device(device.id, area_id=area.id)
    migrate(hass, local, snapshot())
    moved = er.async_get(hass).async_get(entity.entity_id)
    assert dr.async_get(hass).async_get(moved.device_id).area_id == area.id


async def test_loaded_old_entity_blocks_migration_before_changes(hass):
    _old, local, _device, entity = old_measurement(hass)
    with (
        patch(
            "custom_components.terrestream_local.migration.entity_sources",
            return_value={entity.entity_id: {}},
        ),
        pytest.raises(ConfigEntryNotReady),
    ):
        migrate(hass, local, snapshot())
    assert er.async_get(hass).async_get(entity.entity_id).platform == "mqtt"


async def test_migration_no_source_is_actionable_and_completed_moves_are_idempotent(
    hass,
):
    local = config_entry()
    local.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        local, data={**local.data, "legacy_source": "mqtt"}
    )
    with pytest.raises(ConfigEntryNotReady):
        migrate(hass, local, snapshot())
    er.async_get(hass).async_get_or_create(
        "sensor", "terrestream_local", f"{UUID}_co2", config_entry=local
    )
    migrate(hass, local, snapshot())


async def test_existing_destination_area_is_preserved(hass):
    _old, local, _device, _entity = old_measurement(hass)
    area = ar.async_get(hass).async_create("Office")
    devices = dr.async_get(hass)
    destination = devices.async_get_or_create(
        config_entry_id=local.entry_id, identifiers={("terrestream_local", UUID)}
    )
    devices.async_update_device(destination.id, area_id=area.id)
    migrate(hass, local, snapshot())
    assert devices.async_get(destination.id).area_id == area.id


@pytest.mark.parametrize("offline", [False, True])
async def test_failed_migration_releases_session_and_creates_repair(hass, offline):
    from homeassistant.helpers import issue_registry as ir

    from custom_components.terrestream_local import async_setup_entry

    entry = config_entry()
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, "legacy_source": "mqtt"}
    )
    with patch("custom_components.terrestream_local.Client", autospec=True) as factory:
        client = factory.return_value
        client.identity.return_value = {"paired": True}
        client.refresh.return_value = snapshot()

        async def command(method, **arguments):
            if method == "release" and offline:
                raise ClientError("offline")

        client.command.side_effect = command
        entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)
        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, entry)
        client.command.assert_any_await("release")
        assert (
            ir.async_get(hass).async_get_issue(
                "terrestream_local", f"migration_{entry.entry_id}"
            )
            is not None
        )
