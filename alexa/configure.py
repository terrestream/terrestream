"""Prepare one dedicated Alexa bridge from a real Terrestream HA device.

Default is preflight only. Credentials stay in the selected private bridge home.
Existing helpers are reused only after their complete relevant options match.
"""

import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

import aiohttp
from compat import (
    VOC_HELPER,
    bridge_config,
    choose_sources,
    helper_definitions,
)
from patch import patched_module

ROOT = Path(__file__).resolve().parent
PACKAGE = ROOT / "node_modules/matterbridge-hass"
MODULE = PACKAGE / "dist/module.js"
ADAPTER = PACKAGE / "dist/terrestream-alexa-voc.mjs"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def private_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not isinstance(data, bytes):
        data = (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode()
    temporary = path.with_name(path.name + ".tmp")
    with os.fdopen(
        os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb"
    ) as stream:
        stream.write(data)
    os.replace(temporary, path)
    path.chmod(0o600)


def defaults_from_schema(schema):
    output = {}
    for field in schema:
        name = field["name"]
        if "schema" in field:
            output[name] = defaults_from_schema(field["schema"])
        elif "suggested_value" in field.get("description", {}):
            output[name] = field["description"]["suggested_value"]
        elif "default" in field:
            output[name] = field["default"]
    return output


def verify_helper_options(actual, expected):
    for key in (
        "state",
        "device_id",
        "state_class",
        "device_class",
        "unit_of_measurement",
        "additional_options",
    ):
        if actual.get(key) != expected.get(key):
            raise ValueError(
                "An existing helper has different "
                + key
                + "; leave it intact and resolve the name conflict"
            )


class HomeAssistant:
    def __init__(self, session, url, token):
        self.session, self.url, self.token = session, url, token
        self.ws_url = url.replace("https://", "wss://").replace("http://", "ws://")

    async def request(self, method, path, payload=None):
        async with self.session.request(
            method,
            self.url + path,
            json=payload,
            headers={"Authorization": "Bearer " + self.token},
            allow_redirects=False,
        ) as response:
            if not 200 <= response.status < 300:
                raise ValueError(
                    "Home Assistant request failed (HTTP " + str(response.status) + ")"
                )
            return await response.json()

    async def ws(self, kind, **data):
        async with self.session.ws_connect(self.ws_url + "/api/websocket") as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": self.token})
            if (await ws.receive_json()).get("type") != "auth_ok":
                raise ValueError("Home Assistant authorization failed")
            await ws.send_json({"id": 1, "type": kind, **data})
            reply = await ws.receive_json()
            if not reply.get("success"):
                raise ValueError("Home Assistant operation failed: " + kind)
            return reply["result"]

    async def check_helper(self, entity, expected):
        if (
            entity.get("platform") != "template"
            or entity.get("device_id") != expected["device_id"]
            or entity.get("disabled_by")
        ):
            raise ValueError(
                "Existing helper must be an enabled Template on the selected device"
            )
        path = "/api/config/config_entries/options/flow"
        flow = await self.request("POST", path, {"handler": entity["config_entry_id"]})
        try:
            if flow.get("type") != "form" or flow.get("step_id") != "sensor":
                raise ValueError("Could not inspect existing Template helper")
            verify_helper_options(defaults_from_schema(flow["data_schema"]), expected)
        finally:
            if flow.get("flow_id"):
                await self.request("DELETE", path + "/" + flow["flow_id"])

    async def create_helper(self, expected):
        base = "/api/config/config_entries/flow"
        flow = await self.request(
            "POST", base, {"handler": "template", "show_advanced_options": True}
        )
        path = base + "/" + flow["flow_id"]
        complete = False
        try:
            form = await self.request("POST", path, {"next_step_id": "sensor"})
            if form.get("type") != "form" or form.get("step_id") != "sensor":
                raise ValueError(
                    "Template sensor setup is unsupported by this HA version"
                )
            result = await self.request("POST", path, expected)
            if result.get("type") != "create_entry":
                raise ValueError("Template helper creation failed")
            complete = True
            return result["result"]["entry_id"]
        finally:
            if not complete:
                await self.request("DELETE", path)


async def run(args):
    url = args.ha_url.rstrip("/")
    parsed = urlsplit(url)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "Use an http(s) Home Assistant origin with no path or credentials"
        )
    token = args.token_file.read_text().strip()
    if not token or len(token) > 16384 or "\n" in token:
        raise ValueError(
            "The private token file must contain one Home Assistant access token"
        )
    home = args.home.expanduser().resolve()
    marker = home / "terrestream-alexa.json"
    config_path = home / ".matterbridge/matterbridge-hass.config.json"
    if marker.exists():
        raise ValueError(
            "This companion is already configured; use bridge.mjs check or start"
        )
    if config_path.exists():
        raise ValueError(
            "An existing bridge configuration is present; select a NEW dedicated --home"
        )
    version = json.loads((PACKAGE / "package.json").read_text())["version"]
    pinned = json.loads((ROOT / "upstream.json").read_text())
    original = MODULE.read_bytes()
    if version != "1.5.0" or sha(original) != pinned["module_sha256"]:
        raise ValueError(
            "The plugin is not the pristine pinned build; run npm ci in this companion before setup"
        )
    patched = patched_module(original)
    adapter = (ROOT / "alexa_voc_adapter.mjs").read_bytes()
    defaults = json.loads((PACKAGE / "matterbridge-hass.config.json").read_text())
    created = []
    renamed = False
    previous_name = None
    device_id = None
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=20)
    ) as session:
        ha = HomeAssistant(session, url, token)
        registry = await ha.ws("config/entity_registry/list")
        states = {s["entity_id"]: s for s in await ha.request("GET", "/api/states")}
        device_id, sources = choose_sources(registry, states, args.device_id)
        devices = await ha.ws("config/device_registry/list")
        device = next(d for d in devices if d["id"] == device_id)
        previous_name = device.get("name_by_user")
        if any(
            d["id"] != device_id
            and (d.get("name_by_user") or d.get("name")) == "Terrestream"
            for d in devices
        ):
            raise ValueError(
                "Another HA device is already named Terrestream; resolve the name conflict first"
            )
        definitions = helper_definitions(device_id, sources)
        by_id = {e["entity_id"]: e for e in registry}
        for entity_id, definition in definitions.items():
            if entity_id in by_id:
                await ha.check_helper(by_id[entity_id], definition)
        print(
            json.dumps(
                {
                    "device_name": "Terrestream",
                    "source_entities": sources,
                    "helpers": list(definitions),
                    "alexa_voc_mapping": "Terrestream compatibility index, not a concentration",
                    "co2_in_alexa": False,
                    "apply": args.apply,
                },
                indent=2,
            )
        )
        if not args.apply:
            return
        try:
            home.mkdir(parents=True, exist_ok=True, mode=0o700)
            home.chmod(0o700)
            for entity_id, definition in definitions.items():
                if entity_id not in by_id:
                    entry_id = await ha.create_helper(definition)
                    created.append(entry_id)
                    # Save ownership as soon as it exists, for recovery after interruption.
                    private_write(
                        home / "setup-progress.json",
                        {
                            "created_template_entries": created,
                            "device_id": device_id,
                            "previous_name": previous_name,
                        },
                    )
            for _ in range(40):
                registry = await ha.ws("config/entity_registry/list")
                by_id = {e["entity_id"]: e for e in registry}
                if all(k in by_id for k in definitions):
                    break
                await asyncio.sleep(0.25)
            if not all(k in by_id for k in definitions):
                raise ValueError(
                    "Template entities did not appear with the expected names"
                )
            for entity_id, definition in definitions.items():
                await ha.check_helper(by_id[entity_id], definition)
            if previous_name != "Terrestream":
                await ha.ws(
                    "config/device_registry/update",
                    device_id=device_id,
                    name_by_user="Terrestream",
                )
                renamed = True
            config = bridge_config(
                defaults, token, ha.ws_url, registry, device_id, sources
            )
            private_write(home / "original-module.js", original)
            private_write(ADAPTER, adapter)
            private_write(MODULE, patched)
            private_write(config_path, config)
            private_write(
                marker,
                {
                    "schema": 1,
                    "version": "0.1.2",
                    "device_id": device_id,
                    "source": sources["estimated_tvoc_well"],
                    "helper": VOC_HELPER,
                    "module_sha256": sha(patched),
                    "adapter_sha256": sha(adapter),
                    "original_sha256": sha(original),
                    "created_template_entries": created,
                    "previous_name": previous_name,
                    "package": str(PACKAGE),
                    "voc_enabled": True,
                },
            )
            (home / "setup-progress.json").unlink(missing_ok=True)
        except BaseException:
            # Restore files and only helpers created by this invocation; reused helpers remain intact.
            private_write(MODULE, original)
            ADAPTER.unlink(missing_ok=True)
            config_path.unlink(missing_ok=True)
            marker.unlink(missing_ok=True)
            if renamed:
                await ha.ws(
                    "config/device_registry/update",
                    device_id=device_id,
                    name_by_user=previous_name,
                )
            for entry_id in created:
                await ha.request(
                    "DELETE", "/api/config/config_entries/entry/" + entry_id
                )
            (home / "setup-progress.json").unlink(missing_ok=True)
            raise
    print(
        "Configured. Register this plugin and start the bridge using bridge.mjs. No Alexa pairing has been changed."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ha-url", required=True)
    parser.add_argument("--token-file", required=True, type=Path)
    parser.add_argument("--home", type=Path, default=Path.home() / ".terrestream-alexa")
    parser.add_argument("--device-id")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except (ValueError, AssertionError) as error:
        # Only locally constructed messages; never include remote response bodies or tokens.
        print("Setup stopped: " + str(error), file=sys.stderr)
        raise SystemExit(1) from None
    except (aiohttp.ClientError, OSError, TimeoutError, KeyError, TypeError) as error:
        print(
            "Setup stopped: "
            + type(error).__name__
            + "; check host access, token and pinned dependencies.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
