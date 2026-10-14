"""Boundaries, quantity preservation, source selection and helper ownership."""

import copy
import math
import unittest

from compat import (
    CLASSES,
    IAQ_HELPER,
    KEYS,
    UNITS,
    VOC_HELPER,
    bridge_config,
    choose_sources,
    compatible_index,
    helper_definitions,
)
from configure import defaults_from_schema, verify_helper_options
from patch import patched_module


class CompatibilityTests(unittest.TestCase):
    def test_voc_anchor_values_and_invalid_samples(self):
        for value, expected in [
            (0, 0),
            (145, 12.5),
            (290, 25),
            (475, 45),
            (660, 65),
            (1980, 82.5),
            (3300, 100),
            (4000, 100),
        ]:
            self.assertEqual(compatible_index(value), expected)
        for value in [
            None,
            "",
            "unavailable",
            "unknown",
            "NaN",
            "inf",
            math.nan,
            math.inf,
            -1,
            True,
        ]:
            self.assertIsNone(compatible_index(value))

    def fixture(self):
        registry, states = [], {}
        for key in KEYS:
            entity_id = (
                ("select." if key == "voc_mode" else "sensor.") + "renamed_" + key
            )
            registry.append(
                {
                    "entity_id": entity_id,
                    "unique_id": "physical_" + key,
                    "platform": "terrestream_local",
                    "device_id": "physical",
                    "disabled_by": None,
                }
            )
            attrs = (
                {}
                if key == "voc_mode"
                else {
                    "device_class": CLASSES[key],
                    "unit_of_measurement": UNITS[key][0],
                }
            )
            states[entity_id] = {
                "state": "well" if key == "voc_mode" else "25",
                "attributes": attrs,
            }
        return registry, states

    def test_user_renamed_entities_and_one_writer(self):
        registry, states = self.fixture()
        before = copy.deepcopy((registry, states))
        device_id, sources = choose_sources(registry, states)
        registry += [
            {"entity_id": "switch.private_control", "device_id": device_id},
            {"entity_id": "sensor.other_person", "device_id": "elsewhere"},
        ]
        config = bridge_config(
            {}, "PRIVATE", "ws://ha:8123", registry, device_id, sources
        )
        self.assertEqual(config["whiteList"], ["physical"])
        blocked = config["deviceEntityBlackList"]["Terrestream"]
        self.assertIn(sources["estimated_tvoc_well"], blocked)
        self.assertIn("switch.private_control", blocked)
        self.assertNotIn(VOC_HELPER, blocked)
        self.assertNotIn(IAQ_HELPER, blocked)
        self.assertEqual(config["entityWhiteList"], ["sensor"])
        self.assertEqual((registry[:-2], states), before)
        helpers = helper_definitions(device_id, sources)
        self.assertNotIn("device_class", helpers[VOC_HELPER])
        self.assertNotIn("unit_of_measurement", helpers[VOC_HELPER])

    def test_ambiguous_or_unavailable_sources_are_rejected(self):
        registry, states = self.fixture()
        registry.append(dict(registry[0], device_id="second"))
        with self.assertRaisesRegex(ValueError, "Select one"):
            choose_sources(registry, states)
        choose_sources(registry, states, "physical")
        states["sensor.renamed_co2"]["state"] = "unavailable"
        with self.assertRaisesRegex(ValueError, "current reading"):
            choose_sources(registry, states, "physical")

    def test_wrong_voc_unit_mode_or_disabled_entity_is_rejected(self):
        for mode in ["unit", "mode", "disabled"]:
            registry, states = self.fixture()
            if mode == "unit":
                states["sensor.renamed_estimated_tvoc_well"]["attributes"][
                    "unit_of_measurement"
                ] = "ppm"
            if mode == "mode":
                states["select.renamed_voc_mode"]["state"] = "reset"
            if mode == "disabled":
                registry[-2]["disabled_by"] = "user"
            with self.assertRaises(ValueError):
                choose_sources(registry, states)

    def test_existing_helper_requires_exact_definition(self):
        expected = {
            "state": "correct",
            "device_id": "physical",
            "state_class": "measurement",
            "additional_options": {"availability": "available"},
        }
        verify_helper_options(expected, expected)
        for key, value in [
            ("state", "wrong"),
            ("device_id", "another"),
            ("unit_of_measurement", "µg/m³"),
            ("additional_options", {}),
        ]:
            with self.assertRaises(ValueError):
                verify_helper_options(dict(expected, **{key: value}), expected)
        schema = [
            {"name": "state", "description": {"suggested_value": "correct"}},
            {
                "name": "additional_options",
                "schema": [
                    {
                        "name": "availability",
                        "description": {"suggested_value": "available"},
                    }
                ],
            },
        ]
        self.assertEqual(
            defaults_from_schema(schema),
            {"state": "correct", "additional_options": {"availability": "available"}},
        )

    def test_upstream_changes_fail_before_patching(self):
        with self.assertRaises(AssertionError):
            patched_module(b"unknown module")


if __name__ == "__main__":
    unittest.main()
