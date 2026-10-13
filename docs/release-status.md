# Release status

**Terrestream℠ Indoor Air Quality sensor · October 13, 2026**

| Component | Status |
|---|---|
| Custom integration 0.1.1 | [Published on GitHub](https://github.com/terrestream/terrestream/releases/tag/v0.1.1); manual archive and HACS custom repository |
| Python client 0.1.1 | [Published on PyPI](https://pypi.org/project/terrestream-local/0.1.1/); installed automatically by HA |
| Firmware 4.1.0 | Published fleet-wide through the normal signed server update path |
| HACS default catalog | Not included; add this repository manually |
| HA Core / Works with Home Assistant | Not submitted through this release; acceptance and certification are separate |

Firmware 4.0.72 does not support this protocol. Firmware distribution does not
establish installation on every sensor or completion of all qualification work.

## 0.1.1 compatibility verification — October 13, 2026

Home Assistant's current stable release at verification was **2026.10.1**. Its
image pins Protobuf 7.36.0, which conflicts with client 0.1.0's `protobuf>=5,<7`
requirement. Client **0.1.1 has been public on PyPI since September 26, 2026** and
allows `protobuf>=5,<8`. The integration 0.1.1 release pins that existing client
and imports Probatio directly to match HA's current schema types. Its client
runtime files match the published PyPI wheel byte for byte.

Verified locally:

- All **108 tests** pass on HA **2026.10.1 / Protobuf 7.36.0**, including setup,
  controls, reauthentication, lifecycle, stale readings and package exclusions.
  Lint, formatting and strict typing pass; every integration module exceeds
  95% combined statement/branch coverage.
- The same 108 tests pass on the minimum supported HA **2026.9.3**. CI now
  covers that version as well as the current test environment.
- **28 client tests in each of eight combinations** pass on Python 3.13/3.14
  with Protobuf 5.29.6, 6.33.6, 7.36.0 and 7.36.2. They include a complete
  synthetic Security2 exchange, encrypted bootstrap, pinned TLS identity check
  and rejection of an invalid SRP server proof. Reusing saved credentials alone
  does not exercise Protobuf pairing.
- The local client wheel installs into the official HA 2026.10.1 image with
  HA's actual dependency constraints enforced. No pinned HA dependency was
  downgraded or replaced. The component was installed from the candidate ZIP.
- The physical **R500 bench sensor, firmware 4.1.1**, connects using its saved
  pairing: **35 enabled entities, 12 valid measurements**. CO₂ readings update.
  A dark-theme change and restoration, integration reload and HA restart pass.
  All 37 registered entity IDs (including two disabled estimates) are preserved;
  the sensor's uptime continued increasing through the checks.
- A new eight-digit code from the physical sensor completes the full Security2
  exchange through HA's reauthentication flow on 2026.10.1. HA saves and confirms
  the new pairing, all 12 measurements return, and the old credentials are
  rejected. The existing entry and entity IDs are retained. Recreating the HA
  container with the saved configuration retains the new pairing and restores
  all readings; no errors were logged during that startup.
- The existing local Matterbridge receives readings through the updated HA.
  This verifies internal bridge attributes, not Alexa support.

**Still required before customer recommendation:** a clean HACS installation of
the published integration on the intended HA deployment. The October compatibility
run uses Docker Desktop on macOS, a supplemental lab rather than HA's supported
Linux Container deployment. Alexa commissioning and spoken CO₂ remain a separate
hardware test.

## 0.1.0 release acceptance

The installable archive was verified byte for byte against the successful CI
artifact and installed in official **HA 2026.9.3 on Linux Docker Engine 29.8.1**.
A retail sensor ran the distributed signed firmware **4.1.0**. Testing covered:

- Fresh physical-code pairing, 35 enabled entities and 12 valid measurements.
- Removal and re-pairing; the old pairing credentials were rejected afterward.
- Clock/theme controls, numeric readback and restoration of original preferences.
- Vendor-server update checking, integration reload and HA restart.
- Simultaneous normal cloud uploads and local HA readings.

No unexpected sensor reset was observed during these bounded tests. Earlier
retail testing also verified signed OTA and pairing persistence through a user
power-cycle. CI checks cover integration/client tests, typing, coverage, package
contents, HACS metadata and hassfest.

The user separately accepted an **11.57-hour unsigned bench exercise**. That was
not a seven-day uninterrupted soak: temporary unavailability and cached samples
remain recorded. The earlier Docker Desktop test is supplemental to the Linux run.

## Findings and known limitations

| Finding | Disposition for 0.1.0 |
|---|---|
| Earlier 31 KiB largest block after pairing | Retained as a historical memory-target miss, not relabeled a pass. Both later fresh Linux pairings reported 38 KiB from the first successful observation, with a 34 KiB sampled minimum. No allocation failure or reset was observed. These repeats support bounded release acceptance, not a guarantee of a permanently available 32 KiB block. |
| Reload overlapping an update check | Three deliberate trials recovered automatically in 79.27–79.29 seconds without a sensor reset. The old 60-second controller lease and HA retry account for the delay when maintenance prevents graceful release. The original 50-second test remains failed; recovery is documented as a known limitation. |
| Brief startup interruption | The signed firmware deliberately suspends local TLS for its boot assets check after Wi-Fi/NTP settle. The earlier roughly 10-second interruption recovered automatically and is consistent with this path; no serial marker was captured to prove that individual event's cause. Retained as a documented startup behavior, not an unexplained reset. |

These are engineering observations, not HA-mandated memory thresholds. The 32 KiB
snapshot target and 24 KiB sampled target were not lowered. The first release
accepts the stated bounded behavior while preserving the earlier evidence.

## Qualification still outstanding

- HA OS, end-to-end HACS UI installation, multicast discovery across the test VM,
  routed IPv6, multiple sensors, physical actuators and existing MQTT/cloud migrations.
- WAN-blocked retail cold boot and packet-capture privacy evidence.
- Extended retail load, poor-network and fault recovery, BLE/MQTT/mobile coexistence,
  power-interrupted provisioning, encrypted-storage faults and interrupted-update rollback.
- Independent security review, native-speaker translation acceptance, Core review
  and Works with Home Assistant certification.

These tests were not completed or waived by publishing firmware or this custom
integration. Use the [user guide](user-guide.md) for maintenance recovery and
availability-aware automations. No Core quality tier or official badge is claimed.

[Quick start](../README.md) · [Maintainer release procedure](maintaining.md)
