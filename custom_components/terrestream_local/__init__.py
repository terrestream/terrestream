"""Local Terrestream integration."""

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from terrestream_local import Client, Credentials
from terrestream_local.errors import AuthenticationError, ClientError

from .const import DOMAIN, PLATFORMS
from .coordinator import Coordinator
from .types import TerrestreamConfigEntry

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    from .services import register

    register(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: TerrestreamConfigEntry) -> bool:
    credentials = Credentials(**entry.data["credentials"])
    client = Client(async_get_clientsession(hass), entry.data["host"], credentials)
    try:
        identity = await client.identity()
        if not identity["paired"]:
            await client.confirm()
    except AuthenticationError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="pairing_revoked"
        ) from err
    except ClientError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="device_unavailable"
        ) from err
    coordinator = Coordinator(hass, entry, client)
    entry.runtime_data = coordinator
    await coordinator.async_config_entry_first_refresh()
    from .migration import migrate

    try:
        migrate(hass, entry, coordinator.data)
    except ConfigEntryNotReady:
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"migration_{entry.entry_id}",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="migration_incomplete",
        )
        await coordinator.async_shutdown()
        try:
            await client.command("release")
        except ClientError:
            pass
        raise
    ir.async_delete_issue(hass, DOMAIN, f"migration_{entry.entry_id}")
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def release_on_stop(event: Event) -> None:
        """Avoid waiting for crash-lease expiry after a graceful HA restart."""
        await coordinator.async_shutdown()
        try:
            await client.command("release")
        except ClientError:
            pass  # Offline/crashed clients still use the bounded lease expiry.

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, release_on_stop)
    )
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: TerrestreamConfigEntry
) -> bool:
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_shutdown()
        try:
            await entry.runtime_data.client.command("release")
        except ClientError:
            pass  # A crash/offline device releases its lease after 60 seconds.
        return True
    return False


async def async_remove_entry(
    hass: HomeAssistant, entry: TerrestreamConfigEntry
) -> None:
    """Revoke pairing, or request physical disconnect if the device is offline."""
    client = Client(
        async_get_clientsession(hass),
        entry.data["host"],
        Credentials(**entry.data["credentials"]),
    )
    try:
        await client.refresh()
        await client.command("unpair")
    except ClientError:
        from .const import DOMAIN

        ir.async_create_issue(
            hass,
            DOMAIN,
            "offline_removal",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="offline_removal",
        )
