# Terrestream Local

Connect an R500 directly to Home Assistant over your home Wi-Fi. Pair using the
code on its screen; no broker or Terrestream account is needed. See your local
measurements, change device preferences, and build your own automations. Website
Pro intelligence is not part of this integration.

**4.1.0 qualification candidate.** The integration and client are implemented and
bench tested. The Home Assistant integration is not yet released through Core or HACS. Native
HA is disabled in standard firmware builds. This is not a certified release.
See [release status](docs/release-status.md) for testing and publication status.

## Installation

**Publication is pending.** These customer installation steps apply after the
integration release and its pinned `terrestream-local` package are published.
Until then, use the [development installation](#developer-installation-and-verification).

Requirements: Home Assistant 2026.9.3 or newer, R500 firmware 4.1.0 with native
Home Assistant support enabled, and local network access between them. Internet
access is needed to download the integration and its Python dependency; normal
readings and controls use the local network.

### HACS

1. Install and configure [HACS](https://www.hacs.xyz/docs/use/download/download/).
2. In HACS, open **Custom repositories**, add
   `https://github.com/terrestream/terrestream`, and select **Integration**.
3. Find **Terrestream Local**, select the published integration version, and download it.
4. Restart Home Assistant, then follow **Setup** below.

This repository must be added manually; it is not currently in HACS's default list.
Choose integration releases named `v<version>`. Client tags are for the Python
package and are not Home Assistant integration releases.

### Manual installation

1. Download `terrestream-ha-<version>-custom.zip` from the integration's
   [GitHub release](https://github.com/terrestream/terrestream/releases).
2. Extract it and copy `custom_components/terrestream_local` into Home Assistant's
   configuration directory, preserving that path. The result must be
   `<config>/custom_components/terrestream_local/manifest.json`.
3. Restart Home Assistant. It installs the exact Python dependency declared in the
   integration manifest. A dependency-installation error usually means the
   package is not yet published or PyPI is unreachable.
4. Follow **Setup** below. Do not copy the repository's `src`, `tests` or `tools`
   directories into the Home Assistant configuration directory.

For upgrades, back up HA, select a published integration release in HACS (or replace
only the component directory for manual installs), and restart HA. Device firmware
updates remain separate and use Terrestream's server.

## Setup

After installing the integration:

1. Connect the R500 to Wi-Fi using its existing setup screen. Connect Home
   Assistant to a network that can reach it.
2. If this device already uses MQTT or the older Terrestream cloud component,
   read [migration](docs/migration.md) first to preserve compatible history.
3. On the R500, open **Setup → Home Assistant → Pair**.
4. In HA, open **Settings → Devices & services**, select the discovered
   Terrestream device, and enter its eight-digit code, including any leading zeros.
   The code expires after two minutes. To enter an address manually, choose
   **Add integration → Terrestream Local**.
5. Name the device and choose its HA area. Its entities then appear on the device
   page. Add the measurements you want to your dashboard.

| Setup field | What to enter |
|---|---|
| Device address | The discovered IP address, or the R500's reachable IP address/hostname. No URL, port, or web login. |
| Pairing code | The eight digits shown on the R500 during its pairing window. |
| Existing history | **New setup** unless you have prepared MQTT/cloud entities using the migration guide. |

Discovery normally needs the same local network. Across VLANs, use manual entry
and allow HA to reach the device's TCP ports 6054 during pairing and 6053 for
normal operation. Do not expose these ports to the internet. Address changes found
through discovery are authenticated before being saved. For a manual address
change, choose **Reconfigure** from the integration menu.

## Measurements

| Entity | Meaning / unit | Default |
|---|---|---|
| Carbon dioxide | CO₂, ppm | Enabled |
| PM1, PM2.5, PM4, PM10 | Particulate matter, µg/m³ | Enabled |
| Temperature, humidity | °C, %; HA can convert supported display units | Enabled |
| Pressure, illuminance | hPa, lx | Enabled |
| VOC index, NOx index | Sensor indices, not gas concentrations | Enabled |
| Computed EPA particulate AQI | Instantaneous PM2.5/PM10 proxy using EPA 2024 breakpoints | Enabled |
| Estimated TVOC (WELL), Estimated TVOC (RESET) | Separate estimates derived from VOC index, µg/m³ | Disabled |

The computed particulate index is not a regulatory daily outdoor AQI or AQHI+.
Changing the device's display index does not change this entity's meaning. TVOC
estimates are not separately measured chemical concentrations. Each estimate is
available only when its corresponding device presentation mode is active; their
separate IDs keep their statistics separate.

One snapshot per device is polled every five seconds. Sensor acquisition runs
independently. Air and pressure expire 60 seconds after acquisition; illuminance
expires after 20 seconds. Network delay consumes that remaining lifetime. HA
expires stale data even if a subsequent poll is delayed. Missing, warming, cleaning,
failed, and stale readings become **unavailable**, never zero. Local outages are
not backfilled into HA history.

## Controls

HA reads the R500's current preferences on setup. Pairing does not reset them.
Configuration entities appear in the device's configuration area.

| Controls | Values / behavior |
|---|---|
| Dark theme; Fahrenheit display; 24-hour clock; automatic brightness | On/off. Device display preferences are separate from HA's measurement-unit settings. |
| Display brightness; ring brightness; speaker volume | Integer levels, normally 10–255, 0–64, and 0–10. Controls use the range reported by the device. |
| Quiet hours | Enable/disable; start/end in 24-hour `HH:MM`; quiet display, ring, and volume levels. |
| Touch sounds; notification sounds | On/off. |
| Device language | English or French (Canada). Uses the existing device behavior, including its unit, clock, and index defaults. |
| Device timezone | Device-supported IANA name, such as `America/New_York`. Unsupported zones are rejected. |
| Display air index | EPA AQI or AQHI+. Changes the R500 display. |
| VOC presentation | VOC index, WELL estimate, or RESET estimate. |
| Cloud data sharing | Cloud enabled or Local only; shown only when supported by firmware. |
| Clean sensor fan | Starts sensor cleaning. Air readings are unavailable during cleaning; other valid sources continue. |
| Check for firmware update; Firmware | Checks and installs the version approved by Terrestream's server. Internet access is required. |

Successful preference changes are saved and read back by the device. Conflicting
revisions fail instead of overwriting a concurrent app/device change. Whole-profile
imports are validated, saved atomically, and serialized with BLE preference writes.
No setting needs a manual integration reload.

**Local only** is an explicit opt-out from cloud measurement uploads. The device
purges queued measurement uploads and does not upload those readings later when
cloud sharing is re-enabled. Minimal authenticated update-health traffic may still
contact Terrestream, and firmware updates still use the vendor server. This mode
therefore means no cloud measurement sharing, not zero internet traffic. HA itself
makes no vendor-cloud requests. Cloud enabled is the firmware default; pairing does
not change it. Your website and mobile app will not receive new cloud measurements
while Local only is selected.

The firmware update entity never accepts an arbitrary URL, uploaded binary, or
unapproved version. It reports known catalog versions and durable update outcomes
(`accepted`, `awaiting_validation`, `succeeded`, `rolled_back`, `interrupted`), without an estimated
progress percentage. A failed catalog check leaves the latest version
unknown. Local HA connectivity may briefly stop during an update, BLE onboarding,
or the captive setup portal and recovers when the device resumes its listener.

## Preference profiles

Administrators can use **Developer tools → Actions**:

- **Terrestream Local: Export preferences**: select the connected device. Returns
  a complete schema-1 profile of its display, quiet-hours, sound, and timezone
  settings. The action fails if fresh, complete preferences cannot be obtained.
- **Terrestream Local: Import preferences**: select the connected device and supply
  that complete profile in `profile`. It rejects extra fields, partial profiles,
  invalid ranges, and unsupported timezones before sending a command.

The required `config_entry_id` field selects a loaded Terrestream Local device.
Import additionally requires the `profile` object returned by export. Profiles
exclude identity, pairing credentials, Wi-Fi, account ownership, and cloud-sharing
policy. Exported profiles can be saved with an HA action's response variable.
Changing the cloud-sharing policy always remains a separate deliberate action.

## Automations

Use ordinary HA numeric-state/state triggers and conditions on the entities.
There are no custom device triggers or conditions. Require a numeric, available
measurement before acting. Choose thresholds for your own purpose; this integration
does not supply health advice or reproduce website Pro recommendations.

To install the optional blueprint, open **Settings → Automations & scenes →
Blueprints → Import Blueprint**. Paste the GitHub URL of
[`local_threshold_control.yaml`](blueprints/automation/terrestream/local_threshold_control.yaml)
from the integration release tag you installed, select **Preview**, and confirm.
Then select **Create automation** and choose the measurement, switch, permission
helper, thresholds and dwell time. HACS installation does not import this blueprint.

Blueprint updates are separate from integration updates. **Re-import blueprint**
uses the original source URL, so a release-tag URL stays on that version. To move
to a newer release, back up the installed blueprint file under
`<config>/blueprints/automation/`, replace its contents with the YAML from the new
release, and reload automations. Preserve the installed filename so existing
automations still reference it. Review changes and check each automation afterward.
See [HA's blueprint update instructions](https://www.home-assistant.io/docs/automation/using_blueprints/#updating-an-imported-blueprint-in-yaml).

The optional [threshold-control blueprint](blueprints/automation/terrestream/local_threshold_control.yaml)
provides hysteresis, a continuous dwell time, and a Toggle helper granting explicit
permission to control a switch. For example, use PM2.5 with your purifier switch,
or humidity with a dehumidifier switch. For bedroom CO₂, a notification automation
may be preferable to controlling equipment. Configure one automation owner per
actuator, and follow the equipment manufacturer's operating restrictions.

Missing data cancels pending changes and leaves the actuator in its current state.
Turn the permission helper off before manual control. Failed actuator acknowledgment
pauses automatic control and raises a notification. Restart begins a fresh dwell
period; elapsed time before the restart is not credited.

## Troubleshooting

| Symptom | Recovery |
|---|---|
| Device not discovered | Check Wi-Fi and network routing. Add the integration manually using its IP address. |
| Code rejected or expired | Tap Pair again on the R500; use all eight digits of the new code. |
| Device address changed | Allow authenticated discovery to update it, or use Reconfigure. |
| Reauthentication requested | On the physical device, disconnect HA and start a new pairing window. Complete HA's reauthentication flow to retain the entry and history. |
| Another controller active | Stop duplicate/restored HA instances, wait one minute for the lease, then reload. A displaced instance will not continually fight for control. |
| A reading is unavailable | Allow sensor warm-up or cleaning to finish. Check the device itself; unrelated valid sensors can remain available. |
| Setting rejected as busy | Let pairing, cleaning, or the update finish; retry. |
| Settings conflict | Refresh current device state before trying again. |
| Storage failure | Restart the R500 and retry. Contact Terrestream support if it persists. |
| Migration paused | Follow the setup error and repair notice. Keep old entities/statistics until migration succeeds. |
| Update unavailable | Check the device's internet access and vendor catalog availability; local readings can still work. |

Download diagnostics from the integration menu for support. Diagnostics contain
allowlisted versions, measurement availability, resource health, storage status,
and update outcomes. They omit readings, UUIDs, addresses, tokens, certificates,
and account data. Do not attach HA backups or the standalone client's credentials
file to an issue. Include firmware and HA versions, reproduction steps, and
redacted diagnostics when reporting a problem. Maintainer: `@Xynergi`.
Repository: [terrestream/terrestream](https://github.com/terrestream/terrestream).

## Removal, backups, and ownership

Remove the integration through **Settings → Devices & services**. When online, HA
asks the device to erase its pairing. If offline, HA displays a repair notice:
on that physical device, select **Setup → Home Assistant → Disconnect**, then
confirm. Do this before transferring ownership. Disconnecting HA does not clear
Wi-Fi, Bluetooth bonds, MQTT preferences, or the Terrestream account binding.

HA backups contain the pairing secret. Protect them. Restored credentials can
verify the device and a new address; a second running copy can cause controller
conflict. If credentials are lost, disconnect on the device and pair again. Physical
re-pairing rotates the token and certificate. Deleting an offline HA entry alone
cannot revoke a copied backup. Temporary absence never deletes a device or history.

## Developer installation and verification

Development environment: unsigned R500 firmware 4.1.0, HA 2026.9.3 and
Python 3.14.6. The client supports Python 3.13 or newer. Firmware 4.0.72
does not implement this protocol. See [release status](docs/release-status.md)
for outstanding installation and hardware tests.

In a dedicated environment, from this directory:

```sh
python -m pip install -e . -r requirements-test.txt
python tools/verify.py
python -m build
```

For a disposable HA development instance, install the built client wheel in its
Python environment, copy `custom_components/terrestream_local` into the HA config's
`custom_components` directory, and restart HA. The installed 0.1.0 wheel satisfies
the manifest's exact dependency. HA OS installation requires the client package
to be published on PyPI.

The standalone bench helper `tools/pair_check.py` privately prompts for a code and
stores credentials in an owner-only file outside the repository. It reports
connection and resource status without logging credentials or measurements. See
[protocol](docs/protocol.md), [migration](docs/migration.md), and
[release status](docs/release-status.md).

## Repository layout

- `custom_components/terrestream_local/`: Home Assistant integration and translations.
- `src/terrestream_local/`: standalone Python client and required protocol dependencies.
- `docs/`: [client usage](docs/client.md), [protocol](docs/protocol.md),
  [migration](docs/migration.md), [maintenance](docs/maintaining.md),
  [release status](docs/release-status.md), and [licensing](docs/licensing.md).
- `tests/`: client, integration, blueprint and packaging tests.
- `blueprints/`: optional automation blueprint.
- `tools/`: verification, packaging and development pairing utilities.
- `.github/`: issue form, code ownership and CI workflows.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) for development and pull requests, and
[SECURITY.md](SECURITY.md) to report a vulnerability privately.

## License and marks

Copyright © 2026 Aerodyne Inc. [terrestream.com](https://terrestream.com).

Apache License 2.0. See [LICENSE](LICENSE), [NOTICE](NOTICE),
[licensing and marks](docs/licensing.md), and [third-party notices](THIRD_PARTY_NOTICES.md).
Terrestream is a service mark of Aerodyne Inc. Home Assistant is a trademark of
the Open Home Foundation. Compatibility does not imply certification or endorsement.
