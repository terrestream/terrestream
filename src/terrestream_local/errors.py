"""Errors that contain no credentials, response bodies or device identifiers."""


class ClientError(Exception):
    """Device unavailable or command rejected."""


class AuthenticationError(ClientError):
    """Pairing secret or pinned certificate rejected."""


class ControllerConflict(ClientError):
    """Another running controller owns the device lease."""


class ProtocolError(ClientError):
    """Unsupported or malformed local protocol."""


class TransportError(ClientError):
    """Request outcome is uncertain; an identical command may be retried."""
