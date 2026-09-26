"""Display semantics remain separate from Home Assistant unit preferences."""

from typing import cast

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import Coordinator
from .types import TerrestreamConfigEntry

PARALLEL_UPDATES = 0

from homeassistant.components.select import SelectEntity

from .const import SELECT_SETTINGS
from .entity import Entity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TerrestreamConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    caps = entry.runtime_data.data["capabilities"]["settings"]
    entities: list[SelectEntity] = [
        Select(entry.runtime_data, key, *value)
        for key, value in SELECT_SETTINGS.items()
        if key in caps
    ]
    if entry.runtime_data.data.get("local_only_supported") is True:
        entities.append(CloudPolicy(entry.runtime_data))
    async_add_entities(entities)


class Select(Entity, SelectEntity):
    def __init__(
        self, coordinator: Coordinator, key: str, name: str, options: list[str]
    ) -> None:
        super().__init__(coordinator, key, name, True)
        self._attr_options = options

    @property
    def current_option(self) -> str | None:
        return self.options[cast(int, self.coordinator.data["settings"][self.key])]

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.command(
            "set", key=self.key, value=self.options.index(option)
        )


class CloudPolicy(Entity, SelectEntity):
    """Cloud upload policy; pairing preserves the current setting."""

    def __init__(self, coordinator: Coordinator) -> None:
        super().__init__(coordinator, "cloud_policy", "Cloud data sharing", True)
        self._attr_options = ["cloud_enabled", "local_only"]

    @property
    def current_option(self) -> str | None:
        return self.coordinator.data.get("cloud_policy")

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.command("cloud_policy", mode=option)
