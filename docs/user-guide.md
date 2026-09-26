# User guide

Setup and reference for the **Terrestream℠ Indoor Air Quality sensor**.
Start with the [quick start](../README.md); check [release status](release-status.md)
before installing.

## Installation and upgrades

### HACS

1. [Install HACS](https://www.hacs.xyz/docs/use/download/download/).
2. Open **Custom repositories**. Add `https://github.com/terrestream/terrestream`
   with category **Integration**.
3. Download a published **Terrestream Local** integration release, then restart HA.

The repository is not in HACS's default list. Integration releases use
`v<version>`; client tags use `client-v<version>`.

### Manual

1. Download `terrestream-ha-<version>-custom.zip` from
   [Releases](https://github.com/terrestream/terrestream/releases).
2. Extract `custom_components/terrestream_local` into your HA configuration folder.
   Confirm `<config>/custom_components/terrestream_local/manifest.json` exists.
3. Restart HA. It installs the pinned Python dependency automatically.

Copy only the component folder. A dependency error usually means PyPI is
unreachable or the required package is unavailable.

**Upgrade:** back up HA, update through HACS or replace the component folder,
then restart HA. Sensor firmware updates are separate.

## Network and pairing

| Field or connection | Requirement |
|---|---|
| Device address | Reachable IP address or hostname; no URL or port |
| Pairing code | Eight digits from **Setup → Home Assistant → Pair**; valid for two minutes |
| Existing history | **New setup**, or a prepared [migration](migration.md) |
| Discovery | Usually the same local network |
| Routed networks/VLANs | Manual address entry; allow TCP 6054 for pairing and 6053 for normal use |
| Address changes | Authenticated discovery updates the address; manual setups can use **Reconfigure** |

Keep the local ports off the public internet. Use one active HA controller per
sensor. Pairing needs no Terrestream web account.

## Measurements

| Measurement | Unit | Default |
|---|---|---|
| Carbon dioxide | ppm | Enabled |
| PM1, PM2.5, PM4, PM10 | µg/m³ | Enabled |
| Temperature / humidity | °C / % | Enabled |
| Pressure / illuminance | hPa / lx | Enabled |
| VOC index / NOx index | Index values | Enabled |
| Computed EPA particulate AQI | Index derived from PM2.5/PM10 | Enabled |
| Estimated TVOC: WELL / RESET | µg/m³ derived from VOC index | Disabled |

- HA can convert supported display units. Sensor display settings are separate.
- VOC and NOx indices are not gas concentrations. TVOC values are estimates,
  available only in their matching presentation mode; each has a separate history.
- Computed AQI uses instantaneous readings and EPA 2024 breakpoints. It is not
  a regulatory daily outdoor AQI or AQHI+.
- HA polls every five seconds. Readings expire from acquisition: **60 seconds**
  for air/pressure and **20 seconds** for light. Network delay counts toward expiry.
- Missing, warming, cleaning, failed or stale readings become **unavailable**.
  Other valid readings remain usable. Local outages are not backfilled.

## Controls

| Group | Available settings |
|---|---|
| Display | Dark theme, Fahrenheit, 24-hour clock, automatic brightness |
| Levels | Display brightness 10–255; ring brightness 0–64; volume 0–10, subject to reported capabilities |
| Quiet hours | On/off, start/end in `HH:MM`, quiet display/ring/volume levels |
| Sounds | Touch and notification sounds |
| Language and time | English or French (Canada); supported IANA timezone, such as `America/New_York` |
| Presentation | Display EPA AQI or AQHI+; VOC index, WELL estimate or RESET estimate |
| Maintenance | Clean sensor fan; check/install approved firmware |

Language changes retain the sensor's existing behavior, including unit, clock
and index defaults. Fan cleaning temporarily makes affected air readings unavailable.

Changes are saved and read back. Concurrent edits fail with a conflict instead
of silently overwriting an app or sensor change. No manual HA reload is needed.

### Cloud sharing

| Mode | Measurement uploads | Website and mobile app |
|---|---|---|
| **Cloud enabled** — default | Continue | Receive new cloud readings |
| **Local only** | Stop; queued readings are purged | Receive no new cloud readings |

Re-enabling sharing does not upload readings discarded in Local only mode.
Minimal authenticated update-health requests and server firmware updates may
still use the internet. HA itself makes no Terrestream cloud requests. Pairing
never changes this policy.

### Firmware updates

- Internet access is required; Terrestream's server selects approved versions.
- HA cannot upload a binary or select an arbitrary download URL.
- Update status reports acceptance, validation, success, rollback or interruption;
  it does not estimate a progress percentage. A failed check leaves the latest
  version unknown.
- Local connectivity can pause during checks, updates, Bluetooth onboarding or
  Wi-Fi setup. Allow recovery before reloading the integration.

## Preference profiles

In **Developer tools → Actions**, choose **Terrestream Local: Export preferences**
or **Import preferences** and select the sensor.

- Export returns a complete schema-1 profile; stale or incomplete preferences fail.
- Import takes that complete object in `profile`. Partial profiles, extra fields,
  invalid ranges and unsupported timezones are rejected before writing.
- `config_entry_id` selects the loaded sensor. An action response variable can
  store an exported profile.
- Profiles include display, sound, quiet-hours and timezone settings. They exclude
  identity, pairing secrets, Wi-Fi, ownership and cloud-sharing policy.
- Imports save atomically and serialize with Bluetooth preference writes.

## Automations

Use HA's standard numeric-state or state triggers. Require an available numeric
reading and choose thresholds for your purpose. There are no custom device
triggers, health recommendations or website Pro insights in this integration.

The optional [threshold-control blueprint](../blueprints/automation/terrestream/local_threshold_control.yaml)
adds upper/lower thresholds, a continuous dwell time and a Toggle helper that
permits switch control.

1. Open **Settings → Automations & scenes → Blueprints → Import Blueprint**.
2. Paste the blueprint's GitHub URL from the integration release tag you installed.
   Select **Preview**, then confirm.
3. Select **Create automation**. Choose the reading, switch, permission helper,
   thresholds and dwell time.

HACS does not install the blueprint. Use one automation owner per switch and
follow the equipment's operating restrictions. Turn the permission helper off
before manual control.

| Event | Blueprint behavior |
|---|---|
| Missing data | Cancels pending changes; leaves the switch in its current state |
| Failed switch acknowledgment | Pauses automatic control and raises a notification |
| HA restart | Starts a fresh dwell period |

**Update a blueprint:** back up its file under `<config>/blueprints/automation/`,
replace its contents with the newer release's YAML, preserve the filename, and
reload automations. Review each affected automation. Re-importing a URL pinned
to a release tag keeps that version. See [HA's update guide](https://www.home-assistant.io/docs/automation/using_blueprints/#updating-an-imported-blueprint-in-yaml).

## Troubleshooting

| Problem | Next step |
|---|---|
| Not discovered | Check Wi-Fi/routing; add the IP address manually |
| Code rejected | Tap **Pair** again; enter all eight new digits |
| Reauthentication requested | Disconnect HA on the sensor, then pair through HA's reauthentication flow to retain history |
| Another controller active | Stop duplicate/restored HA instances, wait one minute, then reload |
| Reading unavailable | Allow warm-up/cleaning to finish; check the sensor and connection |
| Setting busy or conflicting | Finish maintenance, refresh the current state, then retry |
| Storage failure | Restart the sensor and retry; contact support if it persists |
| Migration paused | Follow the repair notice; preserve old entities and statistics |
| Update unavailable | Check internet access and the approved catalog; local readings can still work |

Download diagnostics from the integration menu. Include HA/firmware versions,
reproduction steps and redacted diagnostics in [an issue](https://github.com/terrestream/terrestream/issues).
Diagnostics omit readings, device IDs, addresses, tokens, certificates and account
data. Never attach pairing credentials or a full HA backup. Maintainer: `@Xynergi`.

## Removal and backups

- Remove the integration in **Settings → Devices & services**. Online removal
  asks the sensor to erase its pairing.
- If it is offline, use **Setup → Home Assistant → Disconnect** on the sensor
  and confirm. Complete this before transferring ownership.
- Disconnecting HA preserves Wi-Fi, Bluetooth bonds, MQTT preferences and account
  binding. Temporary absence does not delete HA history.
- Protect HA backups: they contain the pairing secret. Avoid running two restored
  copies at once.
- If credentials are lost or exposed, disconnect on the sensor and pair again.
  This rotates the token and certificate. Deleting an offline HA entry alone
  cannot revoke a copied backup.
