"""Registry migration preserves statistics identity and unrelated entities."""

from types import SimpleNamespace

import pytest
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.terrestream_local.migration import migrate

from .test_client import UUID, snapshot
from .test_integration import config_entry


@pytest.mark.parametrize(
    "source,old_key",
    [("mqtt", f"{UUID}_co2"), ("terrestream", "terrestream_42_co2_ppm")],
)
async def test_migration_keeps_history_entity_id_and_other_device(
    hass, source, old_key
):
    registry = er.async_get(hass)
    devices = dr.async_get(hass)
    old_config = MockConfigEntry(domain=source)
    old_config.add_to_hass(hass)
    old_device = devices.async_get_or_create(
        config_entry_id=old_config.entry_id, identifiers={(source, UUID)}
    )
    old = registry.async_get_or_create(
        "sensor",
        source,
        old_key,
        config_entry=old_config,
        device_id=old_device.id,
        suggested_object_id="bedroom_co2",
        unit_of_measurement="ppm",
        capabilities={"state_class": "measurement"},
    )
    registry.async_update_entity(old.entity_id, name="My bedroom")
    unrelated = registry.async_get_or_create(
        "sensor", source, "other_device_co2", config_entry=old_config
    )
    insight = registry.async_get_or_create(
        "sensor",
        source,
        "terrestream_42_insight_ventilation_coach",
        config_entry=old_config,
    )
    local = config_entry()
    local.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        local, data={**local.data, "legacy_source": source}
    )
    if source == "terrestream":
        hass.data[source] = {
            old_config.entry_id: SimpleNamespace(
                last_update_success=True,
                disable_raw_signals=True,
                data={"devices": {42: {"meta": {"device_uuid": UUID}}}},
            )
        }
    migrate(hass, local, snapshot())
    moved = registry.async_get(old.entity_id)
    assert moved.platform == "terrestream_local"
    assert moved.config_entry_id == local.entry_id
    assert moved.name == "My bedroom"
    assert moved.unique_id == f"{UUID}_co2"
    assert moved.entity_id == "sensor.bedroom_co2"
    assert registry.async_get(unrelated.entity_id).platform == source
    assert registry.async_get(insight.entity_id).platform == source
    assert moved.device_id != old_device.id
    migrate(hass, local, snapshot())  # Saved completion makes a reload a no-op.


async def test_migration_checks_all_candidates_before_moving_any(hass):
    registry = er.async_get(hass)
    old = MockConfigEntry(domain="mqtt")
    old.add_to_hass(hass)
    valid = registry.async_get_or_create(
        "sensor",
        "mqtt",
        f"{UUID}_co2",
        config_entry=old,
        unit_of_measurement="ppm",
        capabilities={"state_class": "measurement"},
    )
    registry.async_get_or_create(
        "sensor",
        "mqtt",
        f"{UUID}_temperature",
        config_entry=old,
        unit_of_measurement="unknown",
        capabilities={"state_class": "measurement"},
    )
    local = config_entry()
    local.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        local, data={**local.data, "legacy_source": "mqtt"}
    )
    with pytest.raises(ConfigEntryNotReady):
        migrate(hass, local, snapshot())
    assert registry.async_get(valid.entity_id).platform == "mqtt"


async def test_cloud_identity_is_never_inferred_from_names(hass):
    local = config_entry()
    local.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        local, data={**local.data, "legacy_source": "terrestream"}
    )
    with pytest.raises(ConfigEntryNotReady):
        migrate(hass, local, snapshot())


async def test_migration_restores_prior_ownership_after_registry_failure(hass):
    from unittest.mock import patch

    registry = er.async_get(hass)
    old = MockConfigEntry(domain="mqtt")
    old.add_to_hass(hass)
    for key, unit in [("co2", "ppm"), ("temperature", "°C")]:
        registry.async_get_or_create(
            "sensor",
            "mqtt",
            f"{UUID}_{key}",
            config_entry=old,
            unit_of_measurement=unit,
            capabilities={"state_class": "measurement"},
        )
    local = config_entry()
    local.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        local, data={**local.data, "legacy_source": "mqtt"}
    )
    original = registry.async_update_entity_platform
    count = 0

    def fail_second(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 2:
            raise ValueError("injected registry failure")
        return original(*args, **kwargs)

    with (
        patch.object(registry, "async_update_entity_platform", side_effect=fail_second),
        pytest.raises(ConfigEntryNotReady),
    ):
        migrate(hass, local, snapshot())
    assert all(e.platform == "mqtt" for e in registry.entities.values())
    assert local.data["legacy_source"] == "mqtt"


async def test_migration_rejects_existing_destination_history(hass):
    registry = er.async_get(hass)
    old = MockConfigEntry(domain="mqtt")
    old.add_to_hass(hass)
    registry.async_get_or_create(
        "sensor",
        "mqtt",
        f"{UUID}_co2",
        config_entry=old,
        unit_of_measurement="ppm",
        capabilities={"state_class": "measurement"},
    )
    local = config_entry()
    local.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        local, data={**local.data, "legacy_source": "mqtt"}
    )
    registry.async_get_or_create(
        "sensor", "terrestream_local", f"{UUID}_co2", config_entry=local
    )
    with pytest.raises(ConfigEntryNotReady):
        migrate(hass, local, snapshot())
