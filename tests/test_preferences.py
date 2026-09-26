"""Profiles never carry identity, authorization or data-sharing policy."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError

from terrestream_local import Credentials
from terrestream_local.preferences import RANGES, export_profile, validate_profile

from .test_client import TOKEN, UUID, snapshot
from .test_integration import config_entry


def profile():
    return {
        "schema": 1,
        "settings": {
            **{key: limits[0] for key, limits in RANGES.items()},
            "timezone": "America/New_York",
        },
    }


def test_export_is_allowlisted_detached_and_complete():
    settings = profile()["settings"] | {
        "token": "secret",
        "cloud_policy": "local_only",
        "uuid": UUID,
    }
    exported = export_profile(settings)
    assert exported == profile()
    exported["settings"]["dark_mode"] = 1
    assert settings["dark_mode"] == 0
    with pytest.raises(ValueError):
        export_profile({"dark_mode": 1})


@pytest.mark.parametrize(
    "change",
    [
        lambda p: p.update(token="secret"),
        lambda p: p.update(schema=True),
        lambda p: p["settings"].update(volume=11),
        lambda p: p["settings"].update(dark_mode=True),
        lambda p: p["settings"].update(timezone="../../etc/passwd"),
        lambda p: p["settings"].update(cloud_policy="cloud_enabled"),
        lambda p: p["settings"].pop("volume"),
    ],
)
def test_import_rejects_invalid_and_privileged_fields(change):
    value = profile()
    change(value)
    with pytest.raises(ValueError):
        validate_profile(value)


@pytest.mark.asyncio
async def test_profile_actions_and_privacy_control_in_real_ha(
    hass, enable_custom_integrations
):
    entry = config_entry()
    entry.add_to_hass(hass)
    data = snapshot()
    data["settings"] = profile()["settings"]
    data["capabilities"]["preferences_profile"] = 1
    data["local_only_supported"] = True
    data["cloud_policy"] = "cloud_enabled"
    with patch("custom_components.terrestream_local.Client", autospec=True) as factory:
        client = factory.return_value
        client.credentials = Credentials(UUID, "ab" * 32, TOKEN)
        client.identity = AsyncMock(return_value={"paired": True})
        client.refresh = AsyncMock(return_value=data)
        client.command = AsyncMock(return_value={"ok": True})
        client.measurement_remaining.return_value = 60.0
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        exported = await hass.services.async_call(
            "terrestream_local",
            "export_preferences",
            {"config_entry_id": entry.entry_id},
            blocking=True,
            return_response=True,
        )
        assert exported == profile()
        await hass.services.async_call(
            "terrestream_local",
            "import_preferences",
            {"config_entry_id": entry.entry_id, "profile": exported},
            blocking=True,
        )
        client.command.assert_any_await("import_preferences", profile=exported)
        await hass.services.async_call(
            "select",
            "select_option",
            {
                "entity_id": "select.terrestream_r500_cloud_data_sharing",
                "option": "local_only",
            },
            blocking=True,
        )
        client.command.assert_any_await("cloud_policy", mode="local_only")
        bad = profile()
        bad["settings"]["hmac_key"] = "secret"
        calls = client.command.await_count
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "terrestream_local",
                "import_preferences",
                {"config_entry_id": entry.entry_id, "profile": bad},
                blocking=True,
            )
        assert client.command.await_count == calls
        assert await hass.config_entries.async_unload(entry.entry_id)
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "terrestream_local",
                "export_preferences",
                {"config_entry_id": entry.entry_id},
                blocking=True,
                return_response=True,
            )
