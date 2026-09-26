"""Pair a test device and sample its connection and resource status.

Store credentials outside the repository and keep them out of bug reports.
"""

import argparse
import asyncio
import getpass
import json
import os
from dataclasses import asdict
from pathlib import Path

import aiohttp

from terrestream_local import Client, Credentials, pair_device
from terrestream_local.errors import ClientError


async def main(args):
    path = Path(args.credentials).expanduser()
    # Use the OS resolver for .local names; c-ares may not support mDNS.
    connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
    async with aiohttp.ClientSession(connector=connector) as session:
        if args.pair:
            if path.exists():
                raise ValueError("Credential file already exists; choose a new path")
            code = await asyncio.to_thread(getpass.getpass, "Device pairing code: ")
            credentials, client = await pair_device(session, args.host, code)
            # Save credentials before confirmation so pairing remains recoverable.
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as stream:
                json.dump(asdict(credentials), stream)
                stream.flush()
                os.fsync(stream.fileno())
            await client.confirm()
        else:
            if path.stat().st_mode & 0o077:
                raise ValueError("Restrict the credential file permissions to 0600")
            client = Client(
                session, args.host, Credentials(**json.loads(path.read_text()))
            )
        try:
            for _ in range(args.samples):
                try:
                    data = await client.refresh()
                    print(
                        json.dumps(
                            {
                                "protocol": data["protocol"],
                                "firmware": data["firmware"],
                                "uptime_ms": data["uptime_ms"],
                                "health": data.get("health", {}),
                                "measurement_status": {
                                    key: value.get("status")
                                    for key, value in data["measurements"].items()
                                },
                            }
                        ),
                        flush=True,
                    )
                except ClientError:
                    print('{"connection":"unavailable"}', flush=True)
                await asyncio.sleep(5)
        finally:
            try:
                await client.command("release")
            except ClientError:
                pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host")
    parser.add_argument(
        "--credentials", required=True, help="Secret local file outside the repository"
    )
    parser.add_argument("--pair", action="store_true")
    parser.add_argument("--samples", type=int, default=12)
    args = parser.parse_args()
    if not 1 <= args.samples <= 120960:
        parser.error("samples must be between 1 and 120960 (seven days)")
    asyncio.run(main(args))
