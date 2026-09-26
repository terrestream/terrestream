"""Common stable device identity."""

from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import Coordinator


class Entity(CoordinatorEntity[Coordinator]):
    _attr_has_entity_name = True

    def __init__(
        self, coordinator: Coordinator, key: str, name: str, config: bool = False
    ) -> None:
        super().__init__(coordinator)
        self.key = key
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.client.credentials.uuid}_{key}"
        if config:
            self._attr_entity_category = EntityCategory.CONFIG

    @property
    def device_info(self) -> DeviceInfo:
        d = self.coordinator.data
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.client.credentials.uuid)},
            manufacturer="Terrestream",
            model=d["model"],
            sw_version=d["firmware"],
            hw_version=d.get("hardware"),
            name="Terrestream R500",
        )
