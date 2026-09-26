"""Async client; TLS trust is scoped to a physically authenticated device pin."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import math
import re
import struct
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, cast

import aiohttp
from cryptography.exceptions import InvalidTag
from google.protobuf.message import DecodeError

from .errors import (
    AuthenticationError,
    ClientError,
    ControllerConflict,
    ProtocolError,
    TransportError,
)
from .models import Snapshot
from .preferences import validate_profile

MAX_RESPONSE = 16384


def _host(host: str) -> str:
    host = host.strip().strip("[]")
    try:
        address = ipaddress.ip_address(host)
        if "%" in host:
            raise ValueError("Scoped IPv6 is not supported")
        return f"[{address}]" if address.version == 6 else str(address)
    except ValueError:
        if len(host) > 253 or not re.fullmatch(
            r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", host
        ):
            raise ValueError(
                "Enter an IP address or hostname without a URL or port"
            ) from None
        return host


@dataclass(frozen=True)
class Credentials:
    uuid: str
    fingerprint: str = field(repr=False)
    token: str = field(repr=False)
    port: int = 6053

    def __post_init__(self) -> None:
        uuid.UUID(self.uuid)
        if not re.fullmatch(r"[0-9a-f]{64}", self.fingerprint):
            raise ValueError("Invalid device fingerprint")
        if not re.fullmatch(r"[0-9a-f]{64}", self.token):
            raise ValueError("Invalid pairing token")
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError("Invalid port")


async def _body(response: aiohttp.ClientResponse) -> bytes:
    if response.content_length is not None and response.content_length > MAX_RESPONSE:
        raise ProtocolError("Device response exceeds size limit")
    output = bytearray()
    async for part in response.content.iter_chunked(2048):
        output.extend(part)
        if len(output) > MAX_RESPONSE:
            raise ProtocolError("Device response exceeds size limit")
    return bytes(output)


def validate_snapshot(data: dict[str, Any], identity: str) -> Snapshot:
    if data.get("protocol") != 1 or data.get("uuid") != identity:
        raise ProtocolError("Device identity or protocol changed")
    if any(
        not isinstance(data.get(key), str)
        or not re.fullmatch(r"[0-9a-f]{32}", data[key])
        for key in ("session", "boot")
    ):
        raise ProtocolError("Invalid command session")
    if type(data.get("uptime_ms")) is not int or data["uptime_ms"] < 0:
        raise ProtocolError("Invalid device uptime")
    for section in (
        "settings",
        "capabilities",
        "measurements",
        "update",
        "maintenance",
    ):
        if not isinstance(data.get(section), dict):
            raise ProtocolError("Missing device state")
    if type(data.get("settings_revision")) is not int or data["settings_revision"] < 0:
        raise ProtocolError("Invalid settings revision")
    if not isinstance(data["capabilities"].get("settings"), dict):
        raise ProtocolError("Invalid settings capabilities")
    for key, cap in data["capabilities"]["settings"].items():
        if not isinstance(cap, dict) or key not in data["settings"]:
            raise ProtocolError("Invalid setting state")
        value = data["settings"][key]
        if cap.get("type") == "iana_timezone":
            if not isinstance(value, str) or not 1 <= len(value) <= 63:
                raise ProtocolError("Invalid timezone")
        elif (
            type(value) is not int
            or type(cap.get("min")) is not int
            or type(cap.get("max")) is not int
            or not cap["min"] <= value <= cap["max"]
        ):
            raise ProtocolError("Invalid setting range")
    for value in data["measurements"].values():
        if not isinstance(value, dict) or type(value.get("available")) is not bool:
            raise ProtocolError("Invalid measurement availability")
        if value["available"]:
            reading, expires, age = (
                value.get("value"),
                value.get("expires_in_ms"),
                value.get("age_ms"),
            )
            if (
                not isinstance(reading, (int, float))
                or isinstance(reading, bool)
                or not math.isfinite(reading)
                or type(expires) is not int
                or not 0 < expires <= 60000
                or type(age) is not int
                or age < 0
            ):
                raise ProtocolError("Invalid fresh measurement")
    for key in ("model", "firmware"):
        if not isinstance(data.get(key), str) or not 1 <= len(data[key]) <= 48:
            raise ProtocolError("Invalid device metadata")
    return cast(Snapshot, data)


class Client:
    """One serialized controller session per configured device.

    A controller conflict persists until reload or reconfiguration, preventing
    duplicate instances from repeatedly claiming ownership.
    """

    def __init__(
        self, session: aiohttp.ClientSession, host: str, credentials: Credentials
    ) -> None:
        self.session = session
        self.host = _host(host)
        self.credentials = credentials
        self.controller = uuid.uuid4().hex
        self._lock = asyncio.Lock()
        self._sequence = 0
        self._snapshot: Snapshot | None = None
        self._settings_dirty = False
        self._received = 0.0
        self._conflicted = False
        self._pin = aiohttp.Fingerprint(bytes.fromhex(credentials.fingerprint))

    async def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self._conflicted:
            raise ControllerConflict(
                "Another controller is active; stop the duplicate before reloading"
            )
        body = {"controller": self.controller, **payload}
        try:
            async with self.session.post(
                f"https://{self.host}:{self.credentials.port}/rpc",
                json=body,
                ssl=self._pin,
                allow_redirects=False,
                headers={"Authorization": f"Bearer {self.credentials.token}"},
                timeout=aiohttp.ClientTimeout(total=8),
            ) as response:
                if response.status in (401, 403):
                    raise AuthenticationError("Device pairing was revoked")
                if response.status != 200:
                    raise TransportError("Device unavailable or busy")
                data = json.loads(await _body(response))
        except aiohttp.ServerFingerprintMismatch:
            raise AuthenticationError(
                "Device certificate changed; physical re-pairing required"
            ) from None
        except (aiohttp.ClientError, TimeoutError):
            raise TransportError("Cannot reach device") from None
        except (ValueError, TypeError):
            raise ProtocolError("Malformed device response") from None
        if not isinstance(data, dict) or type(data.get("ok")) is not bool:
            raise ProtocolError("Malformed device result")
        if not data["ok"]:
            error = data.get("error", "command_rejected")
            if error == "controller_conflict":
                self._conflicted = self._snapshot is not None
                raise ControllerConflict("Another controller is active")
            if error == "pairing_unconfirmed":
                raise AuthenticationError("Pairing is not confirmed")
            # Do not reflect arbitrary response text into logs.
            raise ClientError(
                error
                if error
                in {
                    "invalid_value",
                    "unsupported_setting",
                    "not_applied",
                    "busy",
                    "session_expired",
                    "command_expired",
                    "storage_failure",
                    "not_started",
                    "revision_conflict",
                    "unsupported_method",
                }
                else "command_rejected"
            )
        return data

    async def identity(self) -> dict[str, Any]:
        """Verify endpoint identity without acquiring or renewing control."""
        async with self._lock:
            data = await self._request({"method": "identity"})
            if (
                data.get("uuid") != self.credentials.uuid
                or data.get("protocol") != 1
                or type(data.get("paired")) is not bool
            ):
                raise AuthenticationError("Authenticated device identity changed")
            return data

    async def confirm(self) -> None:
        async with self._lock:
            await self._request({"method": "confirm"})

    async def _refresh(self) -> Snapshot:
        started = time.monotonic()
        payload = {"method": "snapshot"}
        if self._snapshot:
            payload.update(
                session=self._snapshot["session"], boot=self._snapshot["boot"]
            )
        data = validate_snapshot(await self._request(payload), self.credentials.uuid)
        if self._snapshot is None or self._snapshot["session"] != data["session"]:
            self._sequence = 0
        self._snapshot = data
        self._settings_dirty = False
        self._received = (
            started  # Request latency counts against the remaining sample lifetime.
        )
        return data

    async def refresh(self) -> Snapshot:
        async with self._lock:
            return await self._refresh()

    async def command(self, method: str, **arguments: Any) -> dict[str, Any]:
        if method not in {
            "set",
            "import_preferences",
            "cloud_policy",
            "time",
            "fan_clean",
            "check_update",
            "install_update",
            "unpair",
            "release",
        }:
            raise ValueError("Unsupported operation")
        allowed = {
            "set": {"key", "value"},
            "time": {"epoch", "uncertainty_ms"},
            "import_preferences": {"profile"},
            "cloud_policy": {"mode"},
        }
        if method == "import_preferences":
            arguments["profile"] = validate_profile(arguments.get("profile"))
        if method == "cloud_policy" and arguments.get("mode") not in {
            "cloud_enabled",
            "local_only",
        }:
            raise ValueError("Unsupported cloud policy")
        if set(arguments) - allowed.get(method, set()):
            raise ValueError("Unsupported operation arguments")
        if set(arguments) & {
            "method",
            "controller",
            "session",
            "request_id",
            "expires_ms",
            "boot",
            "expected_revision",
        }:
            raise ValueError("Reserved command fields")
        async with self._lock:
            if (
                self._snapshot is None
                or self._settings_dirty
                or time.monotonic() - self._received > 2
            ):
                await self._refresh()
            assert self._snapshot is not None
            self._sequence += 1
            if self._sequence > 0xFFFFFFFF:
                raise ClientError("Command session exhausted; reconnect")
            # Keep the device-relative expiry and request ID unchanged on retries.
            payload = {
                **arguments,
                "method": method,
                "session": self._snapshot["session"],
                "request_id": self._sequence,
                "boot": self._snapshot["boot"],
                "expires_ms": self._snapshot["uptime_ms"] + 5000,
            }
            if method in {"set", "import_preferences"}:
                payload["expected_revision"] = self._snapshot["settings_revision"]
                # A lost response may still commit a revision; refresh settings before
                # the next operation without extending measurement validity.
                self._settings_dirty = True
            try:
                result = await self._request(payload)
            except TransportError:
                # Retry the same envelope to avoid executing the command twice.
                result = await self._request(payload)
            if result.get("request_id") != self._sequence or result.get(
                "status"
            ) not in {"accepted", "succeeded"}:
                raise ProtocolError("Device did not correlate the command result")
            return result

    def measurement_remaining(self, key: str) -> float:
        if not self._snapshot:
            return 0
        value = self._snapshot["measurements"].get(key)
        if value is None or value["available"] is not True:
            return 0
        return max(
            0,
            value.get("expires_in_ms", 0) / 1000 - (time.monotonic() - self._received),
        )

    def measurement_available(self, key: str) -> bool:
        return self.measurement_remaining(key) > 0


def _validate_pair_response(raw: bytes, step: int) -> None:
    """Bound the upstream protobuf parser inputs and require the exact phase."""
    from ._espressif.proto import sec2_pb2, session_pb2

    message = session_pb2.SessionData()  # type: ignore[attr-defined]  # Generated protobuf descriptor.
    message.ParseFromString(raw)
    field = "sr0" if step == 0 else "sr1"
    expected = (
        sec2_pb2.S2Session_Response0 if step == 0 else sec2_pb2.S2Session_Response1  # type: ignore[attr-defined]
    )
    if (
        message.sec_ver != session_pb2.SecScheme2  # type: ignore[attr-defined]
        or message.WhichOneof("proto") != "sec2"
        or message.sec2.msg != expected
        or message.sec2.WhichOneof("payload") != field
    ):
        raise AuthenticationError("Unexpected pairing phase")
    response = getattr(message.sec2, field)
    if response.status != 0:
        raise AuthenticationError("Pairing proof rejected")
    if step == 0:
        if (
            not 1 <= len(response.device_pubkey) <= 384
            or len(response.device_salt) != 16
        ):
            raise AuthenticationError("Invalid pairing challenge")
    elif len(response.device_proof) != 64 or len(response.device_nonce) != 12:
        raise AuthenticationError("Invalid pairing proof")


async def pair_device(
    session: aiohttp.ClientSession,
    host: str,
    code: str,
    *,
    expected_uuid: str | None = None,
    pair_port: int = 6054,
) -> tuple[Credentials, Client]:
    """Authenticate the displayed pairing code and verify the returned TLS pin.

    Save the returned credentials before confirming the pairing within two
    minutes. Unconfirmed pairings expire. Do not log pairing codes or credentials.
    """
    from ._espressif.security2 import Security2

    if not re.fullmatch(r"[0-9]{8}", code) or not 1 <= pair_port <= 65535:
        raise ValueError("Enter the eight-digit code displayed on the device")
    authority = _host(host)
    security = Security2(1, "terrestream", code, False)

    async def post(path: str, data: bytes | str) -> bytes:
        if isinstance(data, str):
            data = data.encode("latin-1")
        try:
            async with session.post(
                f"http://{authority}:{pair_port}/{path}",
                data=data,
                allow_redirects=False,
                timeout=aiohttp.ClientTimeout(total=8),
            ) as response:
                if response.status != 200:
                    raise AuthenticationError("Pairing failed or expired")
                return await _body(response)
        except (aiohttp.ClientError, TimeoutError):
            raise ClientError("Cannot reach pairing service") from None

    try:
        request = await asyncio.to_thread(security.security_session, None)
        for step in range(2):
            response = await post("pair", request)
            _validate_pair_response(response, step)
            request = await asyncio.to_thread(
                security.security_session, response.decode("latin-1")
            )
        if request is not None:
            raise AuthenticationError("Pairing handshake incomplete")
        encrypted = security.encrypt_data(b"bootstrap")
        bootstrap = json.loads(
            security.decrypt_data(await post("bootstrap", encrypted))
        )
        if bootstrap.get("protocol") != 1:
            raise ProtocolError("Unsupported pairing protocol")
        credentials = Credentials(
            bootstrap["uuid"],
            bootstrap["fingerprint"],
            bootstrap["token"],
            bootstrap["port"],
        )
        if expected_uuid and credentials.uuid != expected_uuid:
            raise AuthenticationError(
                "Discovered device identity did not match pairing"
            )
    except (
        ValueError,
        KeyError,
        TypeError,
        RuntimeError,
        DecodeError,
        InvalidTag,
        struct.error,
        OverflowError,
    ):
        raise AuthenticationError(
            "Pairing proof or device response was invalid"
        ) from None
    client = Client(session, host, credentials)
    await client.identity()
    return credentials, client
