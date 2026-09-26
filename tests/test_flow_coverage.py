"""Pairing, discovery and reauthentication flow tests."""

import ipaddress
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from terrestream_local import Credentials
from terrestream_local.errors import ClientError

from .test_client import TOKEN, UUID
from .test_integration import config_entry


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    yield


def discovery(properties):
    address = ipaddress.ip_address("192.0.2.8")
    return ZeroconfServiceInfo(
        ip_address=address,
        ip_addresses=[address],
        port=6053,
        hostname="device.local.",
        type="_terrestream._tcp.local.",
        name="Device._terrestream._tcp.local.",
        properties=properties,
    )


async def test_new_pairing_and_duplicate(hass):
    credentials = Credentials(UUID, "ab" * 32, TOKEN)
    with (
        patch(
            "custom_components.terrestream_local.config_flow.pair_device",
            return_value=(credentials, None),
        ),
        patch(
            "custom_components.terrestream_local.async_setup_entry", return_value=True
        ),
    ):
        flow = await hass.config_entries.flow.async_init(
            "terrestream_local", context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], {"host": "device.local", "code": "12345678"}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"]["legacy_source"] == "none"
        await hass.async_block_till_done()
        flow = await hass.config_entries.flow.async_init(
            "terrestream_local", context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], {"host": "device.local", "code": "12345678"}
        )
        assert result["reason"] == "already_configured"


async def test_pairing_transport_error(hass):
    with patch(
        "custom_components.terrestream_local.config_flow.pair_device",
        side_effect=ClientError("offline"),
    ):
        flow = await hass.config_entries.flow.async_init(
            "terrestream_local", context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], {"host": "device.local", "code": "12345678"}
        )
        assert result["errors"] == {"base": "cannot_connect"}


async def test_discovery_without_identity_and_new_device(hass):
    result = await hass.config_entries.flow.async_init(
        "terrestream_local", context={"source": "zeroconf"}, data=discovery({})
    )
    assert result["reason"] == "invalid_discovery"
    result = await hass.config_entries.flow.async_init(
        "terrestream_local",
        context={"source": "zeroconf"},
        data=discovery({"uuid": UUID}),
    )
    assert result["type"] is FlowResultType.FORM


@pytest.mark.parametrize(
    "reachable,host", [(True, "old.local"), (True, "192.0.2.8"), (False, "old.local")]
)
async def test_existing_discovery_requires_identity_proof(hass, reachable, host):
    entry = config_entry()
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, data={**entry.data, "host": host})
    with (
        patch(
            "custom_components.terrestream_local.config_flow.Client", autospec=True
        ) as factory,
        patch.object(hass.config_entries, "async_reload", new=AsyncMock()) as reload,
    ):
        factory.return_value.identity = AsyncMock(
            side_effect=None if reachable else ClientError("offline")
        )
        result = await hass.config_entries.flow.async_init(
            "terrestream_local",
            context={"source": "zeroconf"},
            data=discovery({"uuid": UUID}),
        )
        assert result["reason"] == (
            "already_configured" if reachable else "cannot_connect"
        )
        assert entry.data["host"] == ("192.0.2.8" if reachable else host)
        assert reload.await_count == int(reachable and host != "192.0.2.8")


async def test_reauth_retains_identity_and_replaces_credentials(hass):
    entry = config_entry()
    entry.add_to_hass(hass)
    replacement = Credentials(UUID, "cd" * 32, "ef" * 32)
    with (
        patch(
            "custom_components.terrestream_local.config_flow.pair_device",
            return_value=(replacement, None),
        ) as pair,
        patch.object(hass.config_entries, "async_reload", new=AsyncMock()),
    ):
        flow = await hass.config_entries.flow.async_init(
            "terrestream_local",
            context={"source": "reauth", "entry_id": entry.entry_id},
            data=entry.data,
        )
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], {"host": "device.local", "code": "12345678"}
        )
        assert result["reason"] == "reauth_successful"
        assert pair.call_args.kwargs["expected_uuid"] == UUID
        assert entry.data["credentials"]["fingerprint"] == "cd" * 32


async def test_reconfigure_failure_keeps_saved_host(hass):
    entry = config_entry()
    entry.add_to_hass(hass)
    with patch(
        "custom_components.terrestream_local.config_flow.Client", autospec=True
    ) as factory:
        factory.return_value.identity = AsyncMock(side_effect=ClientError("offline"))
        flow = await hass.config_entries.flow.async_init(
            "terrestream_local",
            context={"source": "reconfigure", "entry_id": entry.entry_id},
        )
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], {"host": "bad.local"}
        )
        assert result["errors"]["base"] == "cannot_connect"
        assert entry.data["host"] == "device.local"
