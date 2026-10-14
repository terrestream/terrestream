"""Render the shipped helper templates with HA, including boundary/invalid data."""

import pytest
from homeassistant.helpers.template import Template

from alexa.compat import IAQ_HELPER, VOC_HELPER, compatible_index, helper_definitions


@pytest.mark.parametrize(
    "value,expected",
    [
        (0, "good"),
        (50, "good"),
        (50.001, "fair"),
        (100, "fair"),
        (100.001, "moderate"),
        (150, "moderate"),
        (150.001, "poor"),
        (200, "poor"),
        (200.001, "very_poor"),
        (300, "very_poor"),
        (300.001, "extremely_poor"),
        (500, "extremely_poor"),
        (501, "unknown"),
        (-1, "unknown"),
        ("unavailable", "unknown"),
        ("NaN", "unknown"),
        ("inf", "unknown"),
    ],
)
async def test_iaq_inclusive_firmware_boundaries(hass, value, expected):
    hass.states.async_set("sensor.real_iaq", str(value))
    definition = helper_definitions(
        "physical",
        {
            "computed_epa_aqi": "sensor.real_iaq",
            "estimated_tvoc_well": "sensor.real_tvoc",
        },
    )[IAQ_HELPER]
    assert Template(definition["state"], hass).async_render() == expected
    assert Template(
        definition["additional_options"]["availability"], hass
    ).async_render() == (expected != "unknown")


@pytest.mark.parametrize(
    "value",
    [
        0,
        145,
        288,
        289.99,
        290,
        290.01,
        475,
        659.99,
        660,
        660.01,
        1430,
        1980,
        2200,
        3299.99,
        3300,
        3301,
        100000,
        -1,
        "",
        "unknown",
        "unavailable",
        "NaN",
        "inf",
    ],
)
async def test_voc_template_preserves_concentration_and_rejects_missing(hass, value):
    hass.states.async_set(
        "sensor.real_tvoc", str(value), {"unit_of_measurement": "µg/m³"}
    )
    definition = helper_definitions(
        "physical",
        {
            "computed_epa_aqi": "sensor.real_iaq",
            "estimated_tvoc_well": "sensor.real_tvoc",
        },
    )[VOC_HELPER]
    expected = compatible_index(value)
    actual = Template(definition["state"], hass).async_render()
    assert actual == ("unknown" if expected is None else expected)
    assert Template(
        definition["additional_options"]["availability"], hass
    ).async_render() == (expected is not None)
    assert hass.states.get("sensor.real_tvoc").state == str(value)
    assert "device_class" not in definition
    assert "unit_of_measurement" not in definition
