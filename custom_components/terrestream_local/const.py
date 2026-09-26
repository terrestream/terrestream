"""Local integration constants."""

from homeassistant.const import Platform

DOMAIN = "terrestream_local"
PLATFORMS = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.TEXT,
    Platform.BUTTON,
    Platform.UPDATE,
]
BOOLEAN_SETTINGS = {
    "dark_mode": "Dark theme",
    "fahrenheit": "Fahrenheit display",
    "time_24h": "24-hour clock",
    "auto_brightness": "Automatic brightness",
    "quiet_hours": "Quiet hours",
    "ui_sounds": "Touch sounds",
    "notification_sounds": "Notification sounds",
}
NUMBER_SETTINGS: dict[str, tuple[str, int, int]] = {
    "display_brightness": ("Display brightness", 10, 255),
    "ring_brightness": ("Ring brightness", 0, 64),
    "volume": ("Speaker volume", 0, 10),
    "quiet_display": ("Quiet display brightness", 1, 255),
    "quiet_ring": ("Quiet ring brightness", 0, 64),
    "quiet_volume": ("Quiet speaker volume", 0, 10),
}
SELECT_SETTINGS: dict[str, tuple[str, list[str]]] = {
    "locale": ("Device language", ["en", "fr_ca"]),
    "index_mode": ("Display air index", ["epa_aqi", "aqhi_plus"]),
    "voc_mode": ("VOC presentation", ["voc_index", "well", "reset"]),
}
