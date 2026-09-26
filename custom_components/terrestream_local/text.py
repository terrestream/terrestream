"""Timezone and human-readable quiet-hours times."""

from typing import cast

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .types import TerrestreamConfigEntry

PARALLEL_UPDATES = 0

from homeassistant.components.text import TextEntity
from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN
from .entity import Entity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TerrestreamConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(
        [
            Text(entry.runtime_data, key, name, True)
            for key, name in {
                "timezone": "Device timezone",
                "quiet_start": "Quiet hours start",
                "quiet_end": "Quiet hours end",
            }.items()
            if key in entry.runtime_data.data["capabilities"]["settings"]
        ]
    )


class Text(Entity, TextEntity):
    _attr_native_min = 1
    _attr_native_max = 63

    @property
    def native_value(self) -> str:
        value = self.coordinator.data["settings"][self.key]
        if self.key == "timezone":
            return cast(str, value)
        minutes = cast(int, value)
        return f"{minutes // 60:02d}:{minutes % 60:02d}"

    async def async_set_value(self, value: str) -> None:
        setting: str | int = value
        if self.key != "timezone":
            import re

            if not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", value):
                raise ServiceValidationError(
                    translation_domain=DOMAIN, translation_key="quiet_time"
                )
            h, m = map(int, value.split(":"))
            setting = h * 60 + m
        await self.coordinator.command("set", key=self.key, value=setting)
