"""Firmware updates through the Terrestream server."""

from typing import Any, cast

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .types import TerrestreamConfigEntry

PARALLEL_UPDATES = 0

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN
from .entity import Entity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TerrestreamConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(
        [Update(entry.runtime_data, "firmware_update", "Firmware", True)]
    )


class Update(Entity, UpdateEntity):
    _attr_supported_features = UpdateEntityFeature.INSTALL
    _attr_device_class = UpdateDeviceClass.FIRMWARE

    @property
    def installed_version(self) -> str:
        return self.coordinator.data["firmware"]

    @property
    def latest_version(self) -> str | None:
        return cast(str | None, self.coordinator.data["update"].get("latest_version"))

    @property
    def in_progress(self) -> bool:
        operation = self.coordinator.data.get(
            "update_operation", self.coordinator.data["maintenance"]
        )
        return operation.get("method") == "install_update" and operation.get(
            "status"
        ) in ("accepted", "running", "installing", "awaiting_validation")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        operation = self.coordinator.data.get("update_operation", {})
        return {
            "update_status": operation.get("status", "unknown"),
            "target_version": operation.get("target_version"),
        }

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        if version is not None and version != self.latest_version:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="approved_update"
            )
        await self.coordinator.command("install_update")
