"""Physical-code pairing, manual fallback, rediscovery and reauthentication."""

from dataclasses import asdict
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from terrestream_local import Client, Credentials, pair_device
from terrestream_local.errors import AuthenticationError, ClientError

from .const import DOMAIN


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._host = ""
        self._expected_uuid: str | None = None

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        self._host = discovery_info.host
        self._expected_uuid = discovery_info.properties.get("uuid")
        if not self._expected_uuid:
            return self.async_abort(reason="invalid_discovery")
        await self.async_set_unique_id(self._expected_uuid)
        entry = self.hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, self._expected_uuid
        )
        if entry:
            # Discovery metadata alone never authorizes an endpoint change.
            client = Client(
                async_get_clientsession(self.hass),
                self._host,
                Credentials(**entry.data["credentials"]),
            )
            try:
                await client.identity()
            except ClientError:
                return self.async_abort(reason="cannot_connect")
            if entry.data["host"] != self._host:
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, "host": self._host}
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
            return self.async_abort(reason="already_configured")
        return await self.async_step_user()

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        self._host = entry_data["host"]
        self._expected_uuid = entry_data["credentials"]["uuid"]
        return await self.async_step_user()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            try:
                client = Client(
                    async_get_clientsession(self.hass),
                    user_input["host"],
                    Credentials(**entry.data["credentials"]),
                )
                await client.identity()
            except (ClientError, ValueError):
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={"host": user_input["host"]}
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {vol.Required("host", default=entry.data["host"]): str}
            ),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            try:
                credentials, _client = await pair_device(
                    async_get_clientsession(self.hass),
                    user_input["host"],
                    user_input["code"],
                    expected_uuid=self._expected_uuid,
                )
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except (ClientError, ValueError):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(credentials.uuid)
                data = {"host": user_input["host"], "credentials": asdict(credentials)}
                if self.source != config_entries.SOURCE_REAUTH:
                    data["legacy_source"] = user_input.get("legacy_source", "none")
                if self.source == config_entries.SOURCE_REAUTH:
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(),
                        data_updates=data,
                        reason="reauth_successful",
                    )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Terrestream {credentials.uuid[-6:]}", data=data
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("host", default=self._host): str,
                    vol.Required("code"): str,
                    vol.Optional("legacy_source", default="none"): SelectSelector(
                        SelectSelectorConfig(
                            options=["none", "mqtt", "terrestream"],
                            translation_key="legacy_source",
                        )
                    ),
                }
            ),
            errors=errors,
        )
