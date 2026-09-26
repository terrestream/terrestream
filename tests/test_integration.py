from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from terrestream_local import Credentials
from terrestream_local.errors import AuthenticationError

from .test_client import TOKEN, UUID, snapshot

DOMAIN = "terrestream_local"


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    yield


def config_entry():
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=UUID,
        title="R500",
        data={
            "host": "device.local",
            "credentials": {
                "uuid": UUID,
                "fingerprint": "ab" * 32,
                "token": TOKEN,
                "port": 6053,
            },
        },
    )


@pytest.mark.asyncio
async def test_setup_unload_entities_and_service_readback(hass: HomeAssistant):
    data = snapshot()
    data["settings"].update(
        timezone="America/New_York", quiet_start=1320, quiet_end=420
    )
    entry = config_entry()
    entry.add_to_hass(hass)
    with patch("custom_components.terrestream_local.Client", autospec=True) as factory:
        client = factory.return_value
        client.credentials = Credentials(UUID, "ab" * 32, TOKEN)
        client.identity = AsyncMock(return_value={"paired": True})
        client.measurement_remaining.return_value = 60.0
        client.refresh = AsyncMock(return_value=data)
        client.command = AsyncMock(return_value={"ok": True})
        client.measurement_available.return_value = True
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get("sensor.terrestream_r500_carbon_dioxide").state == "500"
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": "switch.terrestream_r500_dark_theme"},
            blocking=True,
        )
        client.command.assert_any_await("set", key="dark_mode", value=1)
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_wrong_pairing_code_shows_auth_error(hass: HomeAssistant):
    with patch(
        "custom_components.terrestream_local.config_flow.pair_device",
        side_effect=AuthenticationError("wrong code"),
    ):
        flow = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert flow["type"] == FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], {"host": "device.local", "code": "12345678"}
        )
        assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.asyncio
async def test_diagnostics_contains_no_pairing_data(hass: HomeAssistant):
    from custom_components.terrestream_local.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    entry = config_entry()
    from types import SimpleNamespace

    entry.runtime_data = SimpleNamespace(data=snapshot(), last_update_success=True)
    entry.runtime_data.data["health"] = {
        "memory_sampling_active": True,
        "memory_sample_interval_ms": 20,
        "internal_sampled_free_min": 50000,
        "internal_sampled_largest_min": 30000,
        "private_debug": TOKEN,
        "internal_heap_free": TOKEN,
        "internal_largest_block": -1,
    }
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["memory_sampling_active"] is True
    assert result["uptime_ms"] == entry.runtime_data.data["uptime_ms"]
    assert result["resource_health"] == {
        "memory_sample_interval_ms": 20,
        "internal_sampled_free_min": 50000,
        "internal_sampled_largest_min": 30000,
    }
    assert (
        TOKEN not in str(result)
        and UUID not in str(result)
        and "device.local" not in str(result)
    )
    entry.runtime_data.data["uptime_ms"] = TOKEN
    entry.runtime_data.data["health"]["memory_sampling_active"] = TOKEN
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["uptime_ms"] is None
    assert result["memory_sampling_active"] is None
    assert TOKEN not in str(result)


@pytest.mark.asyncio
async def test_setup_confirms_only_after_entry_is_saved(hass):
    entry = config_entry()
    entry.add_to_hass(hass)
    with patch("custom_components.terrestream_local.Client", autospec=True) as factory:
        client = factory.return_value
        client.credentials = Credentials(UUID, "ab" * 32, TOKEN)
        client.identity = AsyncMock(return_value={"paired": False})
        client.refresh = AsyncMock(return_value=snapshot())
        client.measurement_available.return_value = True
        client.measurement_remaining.return_value = 60.0
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        client.confirm.assert_awaited_once()
        assert (
            hass.config_entries.async_get_entry(entry.entry_id).data["credentials"][
                "token"
            ]
            == TOKEN
        )
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        client.command.assert_any_await("release")


@pytest.mark.asyncio
async def test_unreachable_removal_creates_physical_disconnect_issue(hass):
    from homeassistant.helpers import issue_registry as ir

    from custom_components.terrestream_local import async_remove_entry
    from terrestream_local.errors import ClientError

    entry = config_entry()
    entry.add_to_hass(hass)
    with patch("custom_components.terrestream_local.Client", autospec=True) as factory:
        factory.return_value.refresh = AsyncMock(side_effect=ClientError("offline"))
        await async_remove_entry(hass, entry)
    assert ir.async_get(hass).async_get_issue(DOMAIN, "offline_removal") is not None


@pytest.mark.asyncio
async def test_reconfigure_authenticates_without_claiming_lease(hass):
    entry = config_entry()
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.terrestream_local.config_flow.Client", autospec=True
        ) as factory,
        patch(
            "homeassistant.config_entries.ConfigEntries.async_reload", return_value=True
        ),
    ):
        flow = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id}
        )
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], {"host": "192.0.2.10"}
        )
        assert result["type"] == FlowResultType.ABORT
        assert entry.data["host"] == "192.0.2.10"
        factory.return_value.identity.assert_awaited_once()
        factory.return_value.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_diagnostics_restrict_untrusted_status_values(hass):
    from types import SimpleNamespace

    from custom_components.terrestream_local.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    data = snapshot()
    data["measurements"]["co2"]["status"] = TOKEN
    data["maintenance"]["status"] = TOKEN
    entry = config_entry()
    entry.runtime_data = SimpleNamespace(data=data, last_update_success=True)
    result = await async_get_config_entry_diagnostics(hass, entry)
    assert TOKEN not in str(result)


@pytest.mark.asyncio
@pytest.mark.parametrize("offline", [False, True])
async def test_graceful_ha_stop_releases_controller_lease(hass, offline):
    from homeassistant.const import EVENT_HOMEASSISTANT_STOP

    from terrestream_local.errors import TransportError

    entry = config_entry()
    entry.add_to_hass(hass)
    with patch("custom_components.terrestream_local.Client", autospec=True) as factory:
        client = factory.return_value
        client.credentials = Credentials(UUID, "ab" * 32, TOKEN)
        client.identity = AsyncMock(return_value={"paired": True})
        client.refresh = AsyncMock(return_value=snapshot())
        client.measurement_available.return_value = True
        client.measurement_remaining.return_value = 60.0
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        client.command.reset_mock()
        if offline:
            client.command.side_effect = TransportError("offline")
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()
        client.command.assert_awaited_once_with("release")
