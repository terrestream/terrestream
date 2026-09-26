"""Typed config entry runtime."""

from homeassistant.config_entries import ConfigEntry

from .coordinator import Coordinator

type TerrestreamConfigEntry = ConfigEntry[Coordinator]
