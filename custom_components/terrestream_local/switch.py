"""Boolean device preferences."""

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .types import TerrestreamConfigEntry

PARALLEL_UPDATES = 0

from homeassistant.components.switch import SwitchEntity

from .const import BOOLEAN_SETTINGS
from .entity import Entity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TerrestreamConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    caps = entry.runtime_data.data["capabilities"]["settings"]
    async_add_entities(
        [
            Switch(entry.runtime_data, key, name, True)
            for key, name in BOOLEAN_SETTINGS.items()
            if key in caps
        ]
    )


class Switch(Entity, SwitchEntity):
    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data["settings"][self.key])

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.command("set", key=self.key, value=1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.command("set", key=self.key, value=0)
