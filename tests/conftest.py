"""Fixtures for Home Assistant integration tests."""

from pathlib import Path

import custom_components

pytest_plugins = ["pytest_homeassistant_custom_component"]
# The upstream fixture package also supplies a custom_components package.
custom_components.__path__ = [
    str(Path(__file__).resolve().parents[1] / "custom_components"),
    *custom_components.__path__,
]
