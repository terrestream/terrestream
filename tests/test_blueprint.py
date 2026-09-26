from pathlib import Path

from homeassistant.components.automation import config as automation_config
from homeassistant.components.blueprint.models import Blueprint, BlueprintInputs
from homeassistant.components.blueprint.schemas import BLUEPRINT_SCHEMA
from homeassistant.util import yaml


async def test_blueprint_substitutes_and_validates_with_ha(hass):
    data = yaml.load_yaml(
        str(
            Path(__file__).resolve().parents[1]
            / "blueprints/automation/terrestream/local_threshold_control.yaml"
        )
    )
    blueprint = Blueprint(data, expected_domain="automation", schema=BLUEPRINT_SCHEMA)
    inputs = BlueprintInputs(
        blueprint,
        {
            "use_blueprint": {
                "path": "test.yaml",
                "input": {
                    "sensor": "sensor.co2",
                    "actuator": "switch.fan",
                    "enabled": "input_boolean.allow_control",
                    "high": 1000,
                    "low": 800,
                },
            }
        },
    )
    inputs.validate()
    config = inputs.async_substitute()
    assert (
        await automation_config.async_validate_config_item(hass, "automation", config)
        is not None
    )


import asyncio

import pytest
from homeassistant.core import Context, callback
from homeassistant.helpers.script import Script


@pytest.mark.parametrize(
    "reading,initial,expected",
    [
        ("1500", "off", "on"),
        ("500", "on", "off"),
        ("900", "off", "off"),
        ("unavailable", "off", "off"),
    ],
)
async def test_blueprint_hysteresis_and_unknown_data(hass, reading, initial, expected):
    await run_recipe(hass, reading, initial, expected)


async def run_recipe(
    hass, reading, initial, expected, *, interrupt=None, actuator_works=True
):
    data = yaml.load_yaml(
        str(
            Path(__file__).resolve().parents[1]
            / "blueprints/automation/terrestream/local_threshold_control.yaml"
        )
    )
    blueprint = Blueprint(data, expected_domain="automation", schema=BLUEPRINT_SCHEMA)
    config = BlueprintInputs(
        blueprint,
        {
            "use_blueprint": {
                "path": "test.yaml",
                "input": {
                    "sensor": "sensor.co2",
                    "actuator": "switch.fan",
                    "enabled": "input_boolean.allow_control",
                    "high": 1000,
                    "low": 800,
                },
            }
        },
    ).async_substitute()
    # Shorten waits while retaining HA script execution and state listeners.
    for step in config["actions"]:
        if "wait_template" in step:
            step["timeout"] = {"milliseconds": 40}
        if "delay" in step:
            step["delay"] = {"milliseconds": 1}
    validated = await automation_config.async_validate_config_item(
        hass, "automation", config
    )
    assert validated is not None
    hass.states.async_set("sensor.co2", reading)
    hass.states.async_set("switch.fan", initial)
    hass.states.async_set("input_boolean.allow_control", "on")
    calls = []

    @callback
    def service(call):
        calls.append((call.domain, call.service))
        if call.domain == "switch" and actuator_works:
            hass.states.async_set("switch.fan", call.service.removeprefix("turn_"))
        if call.domain == "input_boolean":
            hass.states.async_set("input_boolean.allow_control", "off")

    for domain, name in [
        ("switch", "turn_on"),
        ("switch", "turn_off"),
        ("input_boolean", "turn_off"),
        ("persistent_notification", "create"),
    ]:
        hass.services.async_register(domain, name, service)
    script = Script(hass, validated["actions"], "Threshold recipe", "automation")
    task = hass.async_create_task(script.async_run(config["variables"], Context()))
    if interrupt:
        await asyncio.sleep(0.01)
        hass.states.async_set(*interrupt)
    await task
    assert hass.states.get("switch.fan").state == expected
    return calls


async def test_blueprint_stale_reading_cancels_pending_action(hass):
    calls = await run_recipe(
        hass, "1500", "off", "off", interrupt=("sensor.co2", "unavailable")
    )
    assert not calls


async def test_blueprint_manual_override_cancels_pending_action(hass):
    calls = await run_recipe(
        hass, "1500", "off", "off", interrupt=("input_boolean.allow_control", "off")
    )
    assert not calls


async def test_blueprint_actuator_failure_pauses_automation(hass):
    calls = await run_recipe(hass, "1500", "off", "off", actuator_works=False)
    assert ("input_boolean", "turn_off") in calls
    assert ("persistent_notification", "create") in calls
