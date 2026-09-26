# Changelog

## Python client 0.1.1 — Unreleased

Allow Protobuf 7 for compatibility with the Home Assistant development branch.
Protocol behavior is unchanged. Compatibility tests cover Protobuf 5, 6, and 7
on Python 3.13 and 3.14.

## Python client 0.1.0 — September 26, 2026

Published `terrestream-local` to PyPI from the `client-v0.1.0` tag using Trusted
Publishing. Includes physical-code pairing, pinned local TLS, readings, commands,
preference profiles, and controller-lease handling. Requires Python 3.13 or newer
and firmware 4.1.0 with native HA support enabled. The Home Assistant integration
and retail firmware qualification remain separate.

## Home Assistant integration 0.1.0 — September 26, 2026

The Terrestream℠ Indoor Air Quality sensor connects directly to Home Assistant over local Wi-Fi using the eight-digit
code shown on its screen. Firmware 4.1.0 is required. No account or MQTT broker is
required for local readings and controls.

- Local environmental readings with explicit unavailable/stale behavior.
- Display, lighting, quiet-hours, language, timezone, and speaker controls.
- Complete preference export/import with atomic validation and durable readback.
- Explicit Cloud enabled / Local only choice; pairing preserves the current policy.
- Vendor-approved firmware update checks and installation through the existing server.
- Discovery, authenticated address updates, re-pairing, redacted diagnostics,
  repair notices, and optional compatible history migration.
- English, French, and Spanish Home Assistant text.
- Optional threshold automation with permission, hysteresis, and freshness checks.

Website Pro intelligence is not included. Local only stops cloud measurement
sharing; minimal update-health traffic and server firmware updates still use
internet connectivity.

This is the first public custom integration release. See [release status](docs/release-status.md)
for tested scope and known limitations. It is not certified. HA Core will receive a smaller,
sensor-only initial contribution; the full custom integration is maintained here.
