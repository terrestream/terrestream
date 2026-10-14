# Changelog

## Home Assistant integration 0.1.2 — October 13, 2026

- Publish the optional Alexa Matterbridge companion, with the pinned bridge and
  plugin versions used in the physical Echo Dot test.
- Create HA Template helpers for the firmware IAQ category and a separate
  dimensionless VOC compatibility index; preserve the real HA TVOC concentration.
- Include an opt-in, version-checked bridge adapter for Alexa's 0–100 VOC display,
  one selected Terrestream device, private configuration and a restore command.
- Document the verified app display, pairing recovery, and the remaining CO₂,
  humidity history and voice-query limitations. No CO₂ voice skill is included.
- Keep the published Python client at 0.1.1. No firmware change is required.

See the [Alexa guide](alexa/README.md) and [release status](docs/release-status.md).

## Home Assistant integration 0.1.1 — October 13, 2026

- Require the published `terrestream-local==0.1.1` client, resolving installation
  against Home Assistant 2026.10.1's pinned Protobuf 7.36.0.
- Import Home Assistant's Probatio validation engine directly for setup forms
  and preference services, matching current HA type annotations.
- Verify all 108 tests on HA 2026.10.1 and the minimum supported HA 2026.9.3.
  Test the client on Python 3.13/3.14 with Protobuf 5, 6 and 7, including a full
  synthetic Security2 pairing exchange and invalid-proof rejection.
- Verify fresh physical-code pairing, live readings, controls, reload and restart
  with an R500 sensor running firmware 4.1.1.

See [release status](docs/release-status.md) for tested scope and remaining
qualification. Alexa compatibility is a separate hardware test.

## Python client 0.1.1 — September 26, 2026

Published to PyPI from `client-v0.1.1`. Allows `protobuf>=5,<8`, retaining
Protobuf 5 and 6 support while allowing Protobuf 7. The integration 0.1.1 release
uses this existing package; it does not replace or republish the client.

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
