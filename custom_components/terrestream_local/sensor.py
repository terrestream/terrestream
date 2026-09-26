"""Local readings with acquisition-based expiry."""

from collections.abc import Callable
from datetime import datetime

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import Coordinator
from .types import TerrestreamConfigEntry

PARALLEL_UPDATES = 0

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import callback
from homeassistant.helpers.event import async_call_later

from .entity import Entity

SENSORS: dict[str, tuple[str, SensorDeviceClass | None, str | None]] = {
    "co2": ("Carbon dioxide", SensorDeviceClass.CO2, "ppm"),
    "pm1": ("PM1", SensorDeviceClass.PM1, "µg/m³"),
    "pm25": ("PM2.5", SensorDeviceClass.PM25, "µg/m³"),
    "pm4": ("PM4", None, "µg/m³"),
    "pm10": ("PM10", SensorDeviceClass.PM10, "µg/m³"),
    "temperature": ("Temperature", SensorDeviceClass.TEMPERATURE, "°C"),
    "humidity": ("Humidity", SensorDeviceClass.HUMIDITY, "%"),
    "pressure": ("Pressure", SensorDeviceClass.ATMOSPHERIC_PRESSURE, "hPa"),
    "illuminance": ("Illuminance", SensorDeviceClass.ILLUMINANCE, "lx"),
    "computed_epa_aqi": ("Computed EPA particulate AQI", SensorDeviceClass.AQI, None),
    "voc_index": ("VOC index", None, None),
    "nox_index": ("NOx index", None, None),
    "estimated_tvoc_well": (
        "Estimated TVOC (WELL)",
        SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        "µg/m³",
    ),
    "estimated_tvoc_reset": (
        "Estimated TVOC (RESET)",
        SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
        "µg/m³",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TerrestreamConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(
        [
            Sensor(entry.runtime_data, key, *description)
            for key, description in SENSORS.items()
        ]
    )


class Sensor(Entity, SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: Coordinator,
        key: str,
        name: str,
        device_class: SensorDeviceClass | None,
        unit: str | None,
    ) -> None:
        super().__init__(coordinator, key, name)
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_entity_registry_enabled_default = not key.startswith(
            "estimated_tvoc_"
        )
        self._cancel_expiry: Callable[[], None] | None = None

    @callback
    def _schedule_expiry(self) -> None:
        if self._cancel_expiry:
            self._cancel_expiry()
            self._cancel_expiry = None
        remaining = self.coordinator.client.measurement_remaining(self.key)
        if remaining > 0:
            self._cancel_expiry = async_call_later(self.hass, remaining, self._expire)

    @callback
    def _expire(self, _now: datetime) -> None:
        self._cancel_expiry = None
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._schedule_expiry()
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._schedule_expiry()

    async def async_will_remove_from_hass(self) -> None:
        if self._cancel_expiry:
            self._cancel_expiry()
        await super().async_will_remove_from_hass()

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.client.measurement_available(
            self.key
        )

    @property
    def native_value(self) -> float | int | None:
        return (
            self.coordinator.data["measurements"][self.key].get("value")
            if self.available
            else None
        )
