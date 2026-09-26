"""Authenticated local Terrestream client."""

from .client import Client, Credentials, pair_device
from .errors import AuthenticationError, ClientError, ControllerConflict, ProtocolError

__all__ = [
    "AuthenticationError",
    "Client",
    "ClientError",
    "ControllerConflict",
    "Credentials",
    "ProtocolError",
    "pair_device",
]
