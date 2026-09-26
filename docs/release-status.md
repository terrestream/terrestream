# Release status

**Terrestream℠ Indoor Air Quality sensor · September 26, 2026**

| Component | Status |
|---|---|
| Source and issue tracker | [Public on GitHub](https://github.com/terrestream/terrestream) |
| Python client 0.1.0 | [Published on PyPI](https://pypi.org/project/terrestream-local/0.1.0/); download hashes and a clean install verified |
| Home Assistant integration 0.1.0 | Release pending; HACS and hassfest passed on the client release commit |
| Firmware 4.1.0 | Controlled retail test completed; findings remain open |
| Public firmware catalog | **4.0.72**; the single-device 4.1.0 offer was removed |
| HA Core / Works with Home Assistant | Acceptance and certification pending |

Firmware 4.0.72 does not support this local protocol. The test image enables
native HA explicitly; standard build defaults still leave it disabled.

## Verified so far

- **Bench:** pairing, local TLS, readings, controls, cloud-sharing policy and server
  update integration. The user accepted an 11.57-hour exercise with no detected
  device resets or memory-gate failures. Temporary HA unavailability and cached
  samples remain recorded; this was not a seven-day uninterrupted soak.
- **Retail:** signed OTA, 12 live measurements, saved/restored controls, HA reload
  and restart, concurrent cloud uploads, and pairing persistence through a user
  power-cycle. No unexpected device reset was observed.
- **Published packages:** the public integration files and verified PyPI client
  passed a runtime control check and reboot recovery in Docker Desktop with
  HA 2026.9.3. This does not qualify HA OS or supported Linux Container installation.

## Before release

1. Resolve the initial **31 KiB** pairing-memory result against the **32 KiB**
   snapshot target, slow recovery when reload overlaps an update check, and
   classification of the brief startup HA interruption. Later retail measurements
   reached **38 KiB**; earlier findings remain open.
2. Complete extended-load, fault-recovery, poor-network, BLE/MQTT/mobile coexistence,
   encrypted-storage, interrupted-update and rollback tests.
3. Qualify published-package installation on HA OS/Linux Container, multiple sensors,
   routed IPv6, physical actuators and existing MQTT/cloud migrations.
4. Publish the integration and distribute qualified firmware before the initial
   sensor-only Core contribution, documentation and brand submission.
5. Obtain Works with Home Assistant approval before displaying its badge.

[Quick start](../README.md) · [Maintainer release procedure](maintaining.md)
