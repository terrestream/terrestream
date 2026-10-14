"""Tested IAQ and Alexa-only VOC display mappings. No sensor writes."""

import itertools
import math
import re

VOC_HELPER = "sensor.terrestream_alexa_voc_index"
IAQ_HELPER = "sensor.terrestream_iaq_classification"
ANCHORS = ((0, 0), (290, 25), (660, 65), (3300, 100))


def compatible_index(value):
    if isinstance(value, bool):
        return None
    try:
        concentration = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(concentration) or concentration < 0:
        return None
    for (lower, start), (upper, end) in itertools.pairwise(ANCHORS):
        if concentration <= upper:
            return round(
                start + (concentration - lower) * (end - start) / (upper - lower), 4
            )
    return 100.0


INPUT = "{% set raw = states('__SOURCE__') %}{% set v = raw | float(none) %}"
VALID = "is_number(raw) and raw is not boolean and v >= 0"
CONVERSION = (
    """{%- if not ("""
    + VALID
    + """) -%}unknown
{%- elif v <= 290 -%}{{ (v * 25 / 290) | round(4) }}
{%- elif v <= 660 -%}{{ (25 + (v - 290) * 40 / 370) | round(4) }}
{%- elif v < 3300 -%}{{ (65 + (v - 660) * 35 / 2640) | round(4) }}
{%- else -%}100
{%- endif -%}"""
)
STATE_TEMPLATE = INPUT + CONVERSION
AVAILABILITY_TEMPLATE = INPUT + "{{ " + VALID + " }}"


CLASSIFICATION = """{%- if not is_number(iaq) or iaq < 0 or iaq > 500 -%}
unknown
{%- elif iaq <= 50 -%}good
{%- elif iaq <= 100 -%}fair
{%- elif iaq <= 150 -%}moderate
{%- elif iaq <= 200 -%}poor
{%- elif iaq <= 300 -%}very_poor
{%- else -%}extremely_poor
{%- endif -%}"""
AVAILABILITY = "{{ is_number(iaq) and 0 <= iaq <= 500 }}"
INPUT = "{% set iaq = states('" + "__SOURCE__" + "') | float(none) %}"
IAQ_STATE = INPUT + CLASSIFICATION
IAQ_AVAILABILITY = INPUT + AVAILABILITY


def helper_definitions(device_id, sources):
    return {
        IAQ_HELPER: {
            "name": "Terrestream IAQ classification",
            "device_id": device_id,
            "state": IAQ_STATE.replace("__SOURCE__", sources["computed_epa_aqi"]),
            "additional_options": {
                "availability": IAQ_AVAILABILITY.replace(
                    "__SOURCE__", sources["computed_epa_aqi"]
                )
            },
        },
        VOC_HELPER: {
            "name": "Terrestream Alexa VOC index",
            "device_id": device_id,
            "state": STATE_TEMPLATE.replace(
                "__SOURCE__", sources["estimated_tvoc_well"]
            ),
            "state_class": "measurement",
            "additional_options": {
                "availability": AVAILABILITY_TEMPLATE.replace(
                    "__SOURCE__", sources["estimated_tvoc_well"]
                )
            },
        },
    }


KEYS = (
    "co2",
    "pm25",
    "temperature",
    "humidity",
    "computed_epa_aqi",
    "estimated_tvoc_well",
    "voc_mode",
)
CLASSES = {
    "co2": "carbon_dioxide",
    "pm25": "pm25",
    "temperature": "temperature",
    "humidity": "humidity",
    "computed_epa_aqi": "aqi",
    "estimated_tvoc_well": "volatile_organic_compounds",
}
UNITS = {
    "co2": ("ppm",),
    "pm25": ("µg/m³", "μg/m³"),
    "temperature": ("°C", "°F"),
    "humidity": ("%",),
    "computed_epa_aqi": (None,),
    "estimated_tvoc_well": ("µg/m³", "μg/m³"),
}


def choose_sources(registry, states, device_id=None):
    native = [
        e
        for e in registry
        if e.get("platform") == "terrestream_local" and e.get("device_id")
    ]
    devices = {e["device_id"] for e in native}
    if device_id is None:
        if len(devices) != 1:
            raise ValueError(
                "Select one Terrestream using --device-id; found " + str(len(devices))
            )
        device_id = next(iter(devices))
    if device_id not in devices:
        raise ValueError("Selected device is not a Terrestream Local device")
    sources = {}
    for key in KEYS:
        candidates = [
            e
            for e in native
            if e["device_id"] == device_id
            and e.get("unique_id", "").endswith("_" + key)
        ]
        if len(candidates) != 1 or candidates[0].get("disabled_by"):
            raise ValueError(
                "Enable the selected device's "
                + key
                + " entity in Home Assistant first"
            )
        entity_id = candidates[0]["entity_id"]
        if not re.fullmatch(r"(?:sensor|select)\.[a-z0-9_]+", entity_id):
            raise ValueError("Unexpected entity ID")
        sources[key] = entity_id
        state = states.get(entity_id, {})
        if key == "voc_mode":
            if state.get("state") != "well":
                raise ValueError("Select WELL for the sensor's VOC presentation first")
            continue
        attrs = state.get("attributes", {})
        if (
            attrs.get("device_class") != CLASSES[key]
            or attrs.get("unit_of_measurement") not in UNITS[key]
        ):
            raise ValueError("Unexpected source quantity or unit: " + key)
        try:
            number = float(state.get("state", "nan"))
        except (TypeError, ValueError):
            number = math.nan
        if not math.isfinite(number) or (key != "temperature" and number < 0):
            raise ValueError("A current reading is required: " + key)
    return device_id, sources


def bridge_config(defaults, token, ws_url, registry, device_id, sources):
    selected = {sources[k] for k in ("co2", "pm25", "temperature", "humidity")} | {
        IAQ_HELPER,
        VOC_HELPER,
    }
    blocked = {
        e["entity_id"]
        for e in registry
        if e.get("device_id") == device_id and e["entity_id"] not in selected
    }
    config = dict(defaults)
    config.update(
        host=ws_url,
        token=token,
        rejectUnauthorized=True,
        whiteList=[device_id],
        blackList=[],
        splitEntities=[],
        controllerStrategy="Merge",
        entityWhiteList=["sensor"],
        entityBlackList=[],
        deviceEntityBlackList={"Terrestream": sorted(blocked)},
        filterByArea="",
        filterByLabel="",
        splitByLabel="",
        airQualityRegex="^" + re.escape(IAQ_HELPER) + "$",
        namePostfix="",
        postfix="",
        reconnectTimeout=5,
        reconnectRetries=24,
        debug=False,
        unregisterOnShutdown=False,
    )
    return config
