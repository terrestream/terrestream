"""Opt-in, pre-platform migration using HA's public registry operation."""

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import entity_sources

from terrestream_local.models import Snapshot

from .const import DOMAIN
from .sensor import SENSORS
from .types import TerrestreamConfigEntry

MQTT = {
    key: key
    for key in (
        "co2",
        "pm1",
        "pm25",
        "pm4",
        "pm10",
        "temperature",
        "humidity",
        "pressure",
        "illuminance",
    )
}
MQTT.update(voc="voc_index", nox="nox_index")
CLOUD = dict(
    zip(
        (
            "co2_ppm",
            "pm1p0",
            "pm2p5",
            "pm4p0",
            "pm10p0",
            "temperature_c",
            "humidity_pct",
            "bmp_pressure_hpa",
            "lux",
            "voc_index",
            "nox_index",
        ),
        (
            "co2",
            "pm1",
            "pm25",
            "pm4",
            "pm10",
            "temperature",
            "humidity",
            "pressure",
            "illuminance",
            "voc_index",
            "nox_index",
        ),
        strict=True,
    )
)


def migrate(hass: HomeAssistant, entry: TerrestreamConfigEntry, data: Snapshot) -> None:
    source = entry.data.get("legacy_source", "none")
    if source == "none":
        return
    uuid = entry.data["credentials"]["uuid"]
    registry = er.async_get(hass)
    devices = dr.async_get(hass)
    loaded = entity_sources(hass)
    prefixes = {f"{uuid}_": MQTT} if source == "mqtt" else {}
    if source == "terrestream":
        # Match against the old adapter's authenticated roster without a cloud request.
        for coordinator in hass.data.get("terrestream", {}).values():
            if not getattr(coordinator, "last_update_success", False):
                continue
            if not getattr(coordinator, "disable_raw_signals", False):
                continue
            for device_id, device in (
                (coordinator.data or {}).get("devices", {}).items()
            ):
                if device.get("meta", {}).get("device_uuid") == uuid:
                    prefixes[f"terrestream_{device_id}_"] = CLOUD
        if not prefixes:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN, translation_key="migration_cloud"
            )
    candidates = []
    targets = set()
    for old in registry.entities.values():
        if old.domain != "sensor" or old.platform != source:
            continue
        key = next(
            (
                mapping.get(old.unique_id.removeprefix(prefix))
                for prefix, mapping in prefixes.items()
                if old.unique_id.startswith(prefix)
            ),
            None,
        )
        if key is None:
            continue
        if old.entity_id in loaded:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN, translation_key="migration_active"
            )
        unit = SENSORS[key][2]
        if (
            old.unit_of_measurement != unit
            or (old.capabilities or {}).get("state_class") != "measurement"
        ):
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN, translation_key="migration_units"
            )
        unique_id = f"{uuid}_{key}"
        if key in targets or registry.async_get_entity_id("sensor", DOMAIN, unique_id):
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN, translation_key="migration_duplicate"
            )
        if old.config_entry_id is None:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN, translation_key="migration_owner"
            )
        targets.add(key)
        candidates.append((old, unique_id))
    if not candidates:
        # Idempotent on a retry/restart after all compatible entries moved.
        if any(
            e.platform == DOMAIN and e.config_entry_id == entry.entry_id
            for e in registry.entities.values()
        ):
            return
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="migration_missing"
        )
    device = devices.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, uuid)},
        manufacturer="Terrestream",
        model=data["model"],
        sw_version=data["firmware"],
        name="Terrestream R500",
    )
    changed = []
    try:
        for old, unique_id in candidates:
            registry.async_update_entity_platform(
                old.entity_id,
                DOMAIN,
                new_config_entry_id=entry.entry_id,
                **({"new_unique_id": unique_id} if unique_id != old.unique_id else {}),
                new_device_id=device.id,
            )
            changed.append(old)
    except (ValueError, KeyError) as err:
        for old in reversed(changed):
            current = registry.async_get(old.entity_id)
            assert current is not None and old.config_entry_id is not None
            registry.async_update_entity_platform(
                old.entity_id,
                old.platform,
                new_config_entry_id=old.config_entry_id,
                **(
                    {"new_unique_id": old.unique_id}
                    if current.unique_id != old.unique_id
                    else {}
                ),
                new_device_id=old.device_id,
            )
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="migration_restored"
        ) from err
    # IDs, names, entity areas, disabled states and statistic IDs stay intact.
    if device.area_id is None:
        areas = {
            old.area_id
            or (
                previous.area_id
                if old.device_id and (previous := devices.async_get(old.device_id))
                else None
            )
            for old, _ in candidates
        }
        if len(areas) == 1 and None not in areas:
            devices.async_update_device(device.id, area_id=areas.pop())
    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            "legacy_source": "none",
            "migrated_entity_ids": [old.entity_id for old, _ in candidates],
        },
    )
