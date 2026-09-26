"""Numeric preferences using the ranges reported by the device."""

from typing import cast

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import Coordinator
from .types import TerrestreamConfigEntry

PARALLEL_UPDATES = 0

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN, NUMBER_SETTINGS
from .entity import Entity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TerrestreamConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    caps = entry.runtime_data.data["capabilities"]["settings"]
    async_add_entities(
        [
            Number(entry.runtime_data, key, *value)
            for key, value in NUMBER_SETTINGS.items()
            if key in caps
        ]
    )


class Number(Entity, NumberEntity):
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self, coordinator: Coordinator, key: str, name: str, minimum: int, maximum: int
    ) -> None:
        super().__init__(coordinator, key, name, True)
        cap = coordinator.data["capabilities"]["settings"].get(key, {})
        self._attr_native_min_value = cap.get("min", minimum)
        self._attr_native_max_value = cap.get("max", maximum)

    @property
    def native_value(self) -> int:
        return cast(int, self.coordinator.data["settings"][self.key])

    async def async_set_native_value(self, value: float) -> None:
        if value != int(value):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="whole_number"
            )
        await self.coordinator.command("set", key=self.key, value=int(value))
