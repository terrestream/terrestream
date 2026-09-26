"""Administrator actions for portable preference profiles."""

from typing import Any, cast

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service import async_register_admin_service

from terrestream_local.preferences import export_profile, validate_profile

from .const import DOMAIN
from .coordinator import Coordinator


def register(hass: HomeAssistant) -> None:
    def coordinator(call: ServiceCall) -> Coordinator:
        entry = hass.config_entries.async_get_entry(call.data["config_entry_id"])
        if (
            entry is None
            or entry.domain != DOMAIN
            or entry.state is not ConfigEntryState.LOADED
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="loaded_device"
            )
        if entry.runtime_data.data["capabilities"].get("preferences_profile") != 1:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="profile_unsupported"
            )
        return cast(Coordinator, entry.runtime_data)

    async def export(call: ServiceCall) -> dict[str, Any]:
        device = coordinator(call)
        await device.async_request_refresh()
        if not device.last_update_success:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="profile_unavailable"
            )
        try:
            return export_profile(device.data["settings"])
        except ValueError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="profile_invalid"
            ) from err

    async def restore(call: ServiceCall) -> None:
        device = coordinator(call)
        try:
            profile = validate_profile(call.data["profile"])
        except ValueError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="profile_invalid"
            ) from err
        await device.command("import_preferences", profile=profile)

    async_register_admin_service(
        hass,
        DOMAIN,
        "export_preferences",
        export,
        schema=vol.Schema({vol.Required("config_entry_id"): str}),
        supports_response=SupportsResponse.ONLY,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        "import_preferences",
        restore,
        schema=vol.Schema(
            {vol.Required("config_entry_id"): str, vol.Required("profile"): dict}
        ),
    )
