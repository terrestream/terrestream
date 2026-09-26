# Changelog

## Home Assistant integration 0.1.0 — unreleased

The R500 connects directly to Home Assistant over local Wi-Fi using the eight-digit
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

This is not yet a public installation or certified release. See [release status](docs/release-status.md)
for outstanding tests and publication requirements. HA Core will receive a smaller,
sensor-only initial contribution; the full custom integration is maintained here.
