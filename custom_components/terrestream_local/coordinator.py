"""Poll device state and translate connection and command errors."""

import asyncio
import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from terrestream_local import Client
from terrestream_local.errors import (
    AuthenticationError,
    ClientError,
    ControllerConflict,
)
from terrestream_local.models import Snapshot

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class Coordinator(DataUpdateCoordinator[Snapshot]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: Client) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=5),
        )
        self.client = client
        self.entry = entry
        self._next_clock = 0.0
        self._command_lock = asyncio.Lock()

    async def _async_update_data(self) -> Snapshot:
        try:
            data = await self.client.refresh()
            if time.monotonic() >= self._next_clock:
                await self.client.command(
                    "time", epoch=int(time.time()), uncertainty_ms=1000
                )
                self._next_clock = time.monotonic() + 60
            ir.async_delete_issue(
                self.hass, DOMAIN, f"controller_{self.entry.entry_id}"
            )
            return data
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="pairing_revoked"
            ) from err
        except ControllerConflict as err:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                f"controller_{self.entry.entry_id}",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="controller_conflict",
            )
            raise UpdateFailed(
                "Another controller is active; stop duplicate instances and reload"
            ) from err
        except ClientError as err:
            raise UpdateFailed("Local device unavailable") from err

    async def command(self, method: str, **arguments: Any) -> None:
        try:
            async with self._command_lock:
                await self.client.command(method, **arguments)
                if method not in {"install_update", "check_update", "unpair"}:
                    # A debounced request can return before the new preferences
                    # are read, leaving UI and rapid follow-up actions stale.
                    await self.async_refresh()
        except ClientError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=(
                    str(err)
                    if str(err)
                    in {
                        "busy",
                        "revision_conflict",
                        "storage_failure",
                        "invalid_value",
                        "unsupported_setting",
                        "unsupported_method",
                    }
                    else "command_failed"
                ),
            ) from err
