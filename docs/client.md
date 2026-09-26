# terrestream-local

Asynchronous local client for the **Terrestream℠ Indoor Air Quality sensor**,
separate from its Home Assistant integration. Apache-2.0 licensed; Python 3.13 or newer. Version
0.1.0 targets firmware 4.1.0. Retail firmware qualification and the Home Assistant
integration release remain pending; firmware 4.0.72 does not implement this protocol.

The library accepts a caller-owned `aiohttp.ClientSession`. Physical-code SRP2
pairing establishes a device token and certificate fingerprint; subsequent local
TLS connections authenticate the pinned device. It makes no vendor-cloud calls.
The sensor and client must be reachable on the local network. No MQTT broker or
Terrestream web account is required. See [PROTOCOL.md](https://github.com/terrestream/terrestream/blob/main/docs/protocol.md) for the wire
contract, freshness, exclusive controller lease, retry, and trust behavior.

After obtaining `Credentials` through the physical pairing flow, use:

```python
import aiohttp
from terrestream_local import Client, Credentials

async def read_device(host: str, credentials: Credentials):
    async with aiohttp.ClientSession() as session:
        client = Client(session, host, credentials)
        await client.identity()
        try:
            snapshot = await client.refresh()
            return snapshot
        finally:
            await client.command("release")
```

Keep pairing credentials private. Do not run another controlling client alongside
an active Home Assistant instance. The `tools/pair_check.py` development helper
prompts privately and saves an owner-only credentials file. Do not put that file
in source control, a bug report, or a shared archive.

Source and issues: [terrestream/terrestream](https://github.com/terrestream/terrestream).
Versioned distributions are built in public CI from `client-v<version>` tags
and published using PyPI Trusted Publishing. Vendored Espressif protocol code
retains its upstream license and provenance under `_espressif/`.

## License and marks

Apache License 2.0. See [LICENSE](https://github.com/terrestream/terrestream/blob/main/LICENSE), [NOTICE](https://github.com/terrestream/terrestream/blob/main/NOTICE),
[licensing and marks](https://github.com/terrestream/terrestream/blob/main/docs/licensing.md), and [third-party notices](https://github.com/terrestream/terrestream/blob/main/THIRD_PARTY_NOTICES.md).
Terrestream is a service mark of Aerodyne Inc. Home Assistant is a trademark of
the Open Home Foundation. Compatibility does not imply certification or endorsement.
