"""Sensor cleaning and firmware update checks."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .types import TerrestreamConfigEntry

PARALLEL_UPDATES = 0

from homeassistant.components.button import ButtonEntity

from .entity import Entity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TerrestreamConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(
        [
            Button(entry.runtime_data, key, name, True)
            for key, name in {
                "fan_clean": "Clean sensor fan",
                "check_update": "Check for firmware update",
            }.items()
        ]
    )


class Button(Entity, ButtonEntity):
    async def async_press(self) -> None:
        await self.coordinator.command(self.key)
