import hashlib
import ssl
from datetime import UTC, datetime

import aiohttp
import pytest
import pytest_asyncio
from aiohttp import web
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from terrestream_local import Client, Credentials
from terrestream_local.client import _host, validate_snapshot
from terrestream_local.errors import (
    AuthenticationError,
    ControllerConflict,
    ProtocolError,
)

# Synthetic identity and credentials shared by the protocol tests.
UUID = "00000000-0000-4000-8000-000000000001"
TOKEN = "ab" * 32


def snapshot():
    return {
        "ok": True,
        "uuid": UUID,
        "protocol": 1,
        "session": "cd" * 16,
        "boot": "ef" * 16,
        "uptime_ms": 1000,
        "model": "R500",
        "firmware": "4.1.0",
        "hardware": "test",
        "settings_revision": 1,
        "settings": {"dark_mode": 0},
        "capabilities": {"settings": {"dark_mode": {"min": 0, "max": 1}}},
        "measurements": {
            "co2": {
                "available": True,
                "value": 500,
                "age_ms": 0,
                "expires_in_ms": 50,
                "status": "valid",
            }
        },
        "update": {"checked": False, "latest_version": None},
        "maintenance": {"status": "idle"},
    }


@pytest_asyncio.fixture
async def peer(tmp_path, socket_enabled):
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "physical-device")])
    # Intentionally expired and not matching localhost: pairing pins this exact
    # certificate, independently of wall time and DNS certificate identity.
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(1)
        .not_valid_before(datetime(2000, 1, 1, tzinfo=UTC))
        .not_valid_after(datetime(2001, 1, 1, tzinfo=UTC))
        .sign(key, hashes.SHA256())
    )
    (tmp_path / "cert.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (tmp_path / "key.pem").write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(tmp_path / "cert.pem", tmp_path / "key.pem")
    state = {"calls": [], "reply": None}

    async def rpc(request):
        state["calls"].append(
            {"body": await request.json(), "auth": request.headers.get("Authorization")}
        )
        return web.json_response(
            state["reply"] if state["reply"] is not None else snapshot()
        )

    app = web.Application()
    app.router.add_post("/rpc", rpc)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0, ssl_context=context)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    credentials = Credentials(
        UUID,
        hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest(),
        TOKEN,
        port,
    )
    async with aiohttp.ClientSession() as session:
        yield Client(session, "127.0.0.1", credentials), state
    await runner.cleanup()


@pytest.mark.asyncio
async def test_pin_authenticates_expired_local_cert_and_samples_expire(peer):
    client, state = peer
    await client.refresh()
    assert client.measurement_available("co2")
    assert state["calls"][0]["auth"] == "Bearer " + TOKEN
    client._received -= 1
    assert not client.measurement_available("co2")
    assert not client.measurement_available("missing")


@pytest.mark.asyncio
async def test_wrong_pin_never_sends_bearer(peer):
    client, state = peer
    client._pin = aiohttp.Fingerprint(bytes(32))
    with pytest.raises(AuthenticationError):
        await client.refresh()
    assert state["calls"] == []


@pytest.mark.asyncio
async def test_command_uses_device_relative_expiry_and_correlated_id(peer):
    client, state = peer
    await client.refresh()
    state["reply"] = {"ok": True, "status": "succeeded", "request_id": 1}
    await client.command("set", key="dark_mode", value=1)
    body = state["calls"][-1]["body"]
    assert body["expires_ms"] == 6000
    assert body["request_id"] == 1 and body["session"] == "cd" * 16
    with pytest.raises(ValueError):
        await client.command("set", controller="forged")


@pytest.mark.asyncio
async def test_conflict_latches_without_polling_for_ownership(peer):
    client, state = peer
    await client.refresh()
    state["reply"] = {"ok": False, "error": "controller_conflict"}
    with pytest.raises(ControllerConflict):
        await client.refresh()
    count = len(state["calls"])
    with pytest.raises(ControllerConflict):
        await client.refresh()
    assert len(state["calls"]) == count


@pytest.mark.asyncio
async def test_oversized_response_rejected(peer):
    client, state = peer
    state["reply"] = {"padding": "x" * 20000}
    with pytest.raises(ProtocolError):
        await client.refresh()


@pytest.mark.parametrize(
    "host",
    ["https://example.com", "host/path", "user@host", "host?token=x", "[::1]:6053"],
)
def test_authority_rejects_url_injection(host):
    with pytest.raises(ValueError):
        _host(host)


def test_identity_and_validity_validation():
    data = snapshot()
    data["uuid"] = "wrong"
    with pytest.raises(ProtocolError):
        validate_snapshot(data, UUID)
    for key, value in [
        ("value", float("nan")),
        ("value", True),
        ("age_ms", -1),
        ("expires_in_ms", 0),
    ]:
        data = snapshot()
        data["measurements"]["co2"][key] = value
        with pytest.raises(ProtocolError):
            validate_snapshot(data, UUID)
    data = snapshot()
    data["measurements"]["co2"] = {"available": False, "value": None, "age_ms": None}
    assert validate_snapshot(data, UUID)


def test_credentials_do_not_expose_secrets_in_repr():
    c = Credentials(UUID, "ab" * 32, "cd" * 32)
    assert c.token not in repr(c) and c.fingerprint not in repr(c)


@pytest.mark.asyncio
async def test_uncorrelated_command_result_is_never_success(peer):
    client, state = peer
    await client.refresh()
    state["reply"] = {"ok": True, "status": "succeeded", "request_id": 42}
    with pytest.raises(ProtocolError):
        await client.command("set", key="dark_mode", value=1)
    assert state["calls"][-1]["body"]["expected_revision"] == 1


@pytest.mark.asyncio
async def test_identity_probe_does_not_claim_controller_session(peer):
    client, state = peer
    state["reply"] = {"ok": True, "uuid": UUID, "protocol": 1, "paired": True}
    await client.identity()
    assert client._snapshot is None
    assert state["calls"][-1]["body"]["method"] == "identity"


@pytest.mark.asyncio
async def test_previous_session_is_sent_so_displaced_controller_cannot_reclaim(peer):
    client, state = peer
    await client.refresh()
    await client.refresh()
    assert state["calls"][-1]["body"]["boot"] == "ef" * 16
    assert state["calls"][-1]["body"]["session"] == "cd" * 16


@pytest.mark.asyncio
async def test_initial_busy_device_can_retry_after_crash_lease(peer):
    client, state = peer
    state["reply"] = {"ok": False, "error": "controller_conflict"}
    with pytest.raises(ControllerConflict):
        await client.refresh()
    state["reply"] = snapshot()
    assert await client.refresh()


@pytest.mark.asyncio
async def test_device_reboot_resets_command_sequence(peer):
    client, state = peer
    await client.refresh()
    state["reply"] = {"ok": True, "status": "succeeded", "request_id": 1}
    await client.command("set", key="dark_mode", value=1)
    changed = snapshot()
    changed["session"] = "aa" * 16
    changed["boot"] = "bb" * 16
    state["reply"] = changed
    await client.refresh()
    state["reply"] = {"ok": True, "status": "succeeded", "request_id": 1}
    await client.command("set", key="dark_mode", value=0)
    assert state["calls"][-1]["body"]["session"] == "aa" * 16


@pytest.mark.asyncio
async def test_updater_rejects_arbitrary_url_before_network(peer):
    client, state = peer
    with pytest.raises(ValueError):
        await client.command("install_update", url="https://example.com/firmware.bin")
    assert not state["calls"]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(boot=None),
        lambda d: d.update(settings_revision=True),
        lambda d: d["capabilities"].update(settings=[]),
        lambda d: d["settings"].update(dark_mode=9),
    ],
)
def test_malformed_device_state_rejected(mutate):
    data = snapshot()
    mutate(data)
    with pytest.raises(ProtocolError):
        validate_snapshot(data, UUID)


@pytest.mark.asyncio
async def test_lost_response_retry_uses_identical_envelope(peer):
    from unittest.mock import AsyncMock

    from terrestream_local.errors import TransportError

    client, _ = peer
    await client.refresh()
    client._request = AsyncMock(
        side_effect=[
            TransportError("lost"),
            {"ok": True, "request_id": 1, "status": "accepted"},
        ]
    )
    await client.command("fan_clean")
    assert client._request.await_args_list[0] == client._request.await_args_list[1]


def test_pairing_parser_rejects_wrong_phases_and_nonce_lengths():
    from terrestream_local._espressif.proto import sec2_pb2, session_pb2
    from terrestream_local.client import _validate_pair_response

    msg = session_pb2.SessionData(sec_ver=session_pb2.SecScheme2)
    msg.sec2.msg = sec2_pb2.S2Session_Response0
    msg.sec2.sr0.device_pubkey = b"\x01" * 384
    msg.sec2.sr0.device_salt = b"\x01" * 16
    _validate_pair_response(msg.SerializeToString(), 0)
    with pytest.raises(AuthenticationError):
        _validate_pair_response(msg.SerializeToString(), 1)
    msg.sec2.sr0.device_pubkey = b"\x01" * 385
    with pytest.raises(AuthenticationError):
        _validate_pair_response(msg.SerializeToString(), 0)
    msg.sec2.msg = sec2_pb2.S2Session_Response1
    msg.sec2.sr1.device_proof = b"\x01" * 64
    msg.sec2.sr1.device_nonce = b"\x01" * 12
    _validate_pair_response(msg.SerializeToString(), 1)
    msg.sec2.sr1.device_nonce = b"\x01" * 13
    with pytest.raises(AuthenticationError):
        _validate_pair_response(msg.SerializeToString(), 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("lost_first_result", [False, True])
async def test_rapid_setting_commands_read_new_revision(peer, lost_first_result):
    """Own writes must not look like concurrent external edits, even if ACK is lost."""
    import copy
    from unittest.mock import AsyncMock

    from terrestream_local.errors import TransportError

    client, _ = peer
    device = snapshot()
    calls = []
    lost = 0

    async def respond(payload):
        nonlocal lost
        calls.append(dict(payload))
        if payload["method"] == "snapshot":
            return copy.deepcopy(device)
        if lost_first_result and payload["request_id"] == 1 and lost:
            lost += 1
            raise TransportError("lost acknowledgement again")
        assert payload["expected_revision"] == device["settings_revision"]
        device["settings_revision"] += 1
        device["settings"]["dark_mode"] = payload["value"]
        if lost_first_result and payload["request_id"] == 1:
            lost += 1
            raise TransportError("lost acknowledgement after commit")
        return {"ok": True, "request_id": payload["request_id"], "status": "succeeded"}

    client._request = AsyncMock(side_effect=respond)
    if lost_first_result:
        with pytest.raises(TransportError):
            await client.command("set", key="dark_mode", value=1)
        assert calls[-1] == calls[-2]  # Same envelope for the ambiguous operation.
    else:
        await client.command("set", key="dark_mode", value=1)
    received = client._received
    assert client.measurement_available("co2")  # Dirty settings do not expire sensors.
    await client.command("set", key="dark_mode", value=0)
    assert calls[-2]["method"] == "snapshot"
    assert calls[-1]["expected_revision"] == 2
    assert client._received >= received
    assert device["settings"]["dark_mode"] == 0
