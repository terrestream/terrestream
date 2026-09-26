# Release status

Updated September 26, 2026. **Unpublished integration 0.1.0 for firmware 4.1.0.**
Home Assistant Core acceptance and Works with Home Assistant certification are
pending. Native HA is disabled in standard firmware builds.

Source and the issue tracker are public at
[terrestream/terrestream](https://github.com/terrestream/terrestream).
[Python client 0.1.0](https://pypi.org/project/terrestream-local/0.1.0/) was published
through the reviewed `client-v0.1.0` GitHub workflow using PyPI Trusted Publishing.
The public downloads match the reviewed CI artifacts, and a clean Python install
and import succeeded. HACS and hassfest pass on the client release commit.
The Home Assistant integration remains unreleased; client publication does not
qualify or release the firmware or integration.

## Testing

Local pairing, pinned TLS, readings, controls, cloud-sharing policy and server
update integration have been exercised on one unsigned R500 with HA 2026.9.3.
An 11.57-hour bench run detected no device resets or memory threshold failures.
Menu and BLE activity caused temporary HA unavailability, followed by automatic
recovery. The run did not establish seven-day uninterrupted operation.

## Remaining release work

- Complete fault recovery, network and BLE/MQTT/mobile coexistence testing,
  including memory-reserve stress.
- Test secured retail OTA, encrypted storage, rollback and interrupted updates
  on secured hardware.
- Verify HA OS and Linux Container installation using the published PyPI package,
  including setup, controls, restart and removal.
- Test multiple devices, routed IPv6, physical actuators and migration from
  existing MQTT/cloud installations.
- Publish the integration release after installation and hardware qualification.
- Distribute qualified firmware before submitting the initial sensor-only Core
  contribution, documentation and brand assets.
- Obtain Works with Home Assistant approval before displaying its badge.

See [README.md](../README.md) for supported features and
[MAINTAINING.md](maintaining.md) for packaging and release procedures.
