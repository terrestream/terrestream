# Terrestream in the Alexa app

**Optional companion 0.1.2 · October 13, 2026**

Connect one Terrestream to Alexa through Home Assistant and a dedicated native
Matterbridge. Home Assistant receives the real sensor measurements; this
companion adds the IAQ classification and the VOC display mapping used in our
physical Echo Dot test. This is an advanced, self-hosted setup, separate from
installing the HA integration through HACS.

## What works in this release

| Reading | Alexa device summary | Alexa history/dashboard |
|---|---|---|
| Temperature | Confirmed | Temperature view visible |
| PM2.5 | Confirmed | PM view visible |
| Humidity | Confirmed | Humidity tab absent in our test |
| Overall IAQ category | Confirmed; e.g. Good | Heading derived from firmware cut points |
| VOC compatibility index | Confirmed after the mapping below | VOC display confirmed |
| CO₂ | **Not supported by the tested Alexa path** | Not available |

Spoken CO₂ and humidity queries failed. A temperature question by device name
also failed; a room-temperature answer could have come from the Echo's own
sensor. Spoken VOC has not been verified. Do not promise these voice features
from this release. The full measurements, including CO₂, remain available in HA.
A shared Terrestream Alexa skill is not included.

## Requirements

- Terrestream Local 0.1.2 installed in HA through the
  [HACS custom repository or manual ZIP](https://github.com/terrestream/terrestream/tree/v0.1.2#install).
  The client stays at 0.1.1; no new firmware is required for this companion.
- An always-on host with Python 3.13+ and Node.js 24 or 26. The physical acceptance
  run used HA 2026.10.1 in Docker Desktop and Matterbridge **natively on macOS**.
  Native Linux is a setup option, but this release has not completed that
  companion hardware test. HA OS add-on/container installation is not packaged here.
- An Echo Matter controller on the same normal LAN. We tested an updated
  **Echo Dot (5th generation), Alexa+**, and the Alexa app on an iPhone.
- IPv6 and local multicast connectivity; the Matter service uses UDP **5540**.
  Run this dedicated bridge on a host where that port is available. The iPhone
  needs Local Network permission for Alexa. Avoid guest-network isolation.
- A dedicated bridge paired **only with Alexa**, for the VOC workaround below.

## 1. Prepare the sensor in Home Assistant

Confirm that the paired sensor has current temperature, humidity, PM2.5 and CO₂
readings. On its HA device page, select **WELL** for **VOC presentation**. Enable
its **Estimated TVOC (WELL)** entity if disabled. Wait for a reading in **µg/m³**.
Do not substitute the raw 0–500 VOC index or the RESET estimate.

Create a Home Assistant long-lived access token under your user profile's
Security section. Save it in a private text file **outside the downloaded kit**,
for example `~/.terrestream-ha-token`, and restrict that file to your account:

```sh
chmod 600 "$HOME/.terrestream-ha-token"
```

Treat the token and bridge home as private. Do not upload them to Git or support
issues. The setup tool will place the token in Matterbridge's private config.
This local Matter path does not require entering your Amazon credentials into HA.

## 2. Install the companion

Download `terrestream-alexa-0.1.2.zip` from the
[0.1.2 release](https://github.com/terrestream/terrestream/releases/tag/v0.1.2),
verify its SHA256 against `SHA256SUMS`, extract it and enter its `alexa` folder.
Keep this folder at a stable location on the always-on host.

```sh
npm ci --ignore-scripts --no-audit --no-fund
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Run preflight, replacing the HA address with the address reachable from this
host. Use `http://127.0.0.1:8127` only if that is actually your HA installation;
most installations use `http://homeassistant.local:8123` or a LAN address.

```sh
.venv/bin/python configure.py \
  --ha-url http://homeassistant.local:8123 \
  --token-file "$HOME/.terrestream-ha-token"
```

Preflight makes no persistent changes. If HA has multiple Terrestream devices,
select one with `--device-id` (the ID is at the end of its HA device-page URL).
Only one sensor per companion is supported in this release. Renamed entity IDs
are supported because selection uses the integration's stable identifiers.

Apply the same command with `--apply`:

```sh
.venv/bin/python configure.py \
  --ha-url http://homeassistant.local:8123 \
  --token-file "$HOME/.terrestream-ha-token" --apply
```

This names the selected HA device **Terrestream**, creates two standard Template
helpers on that device, excludes unrelated entities and controls, and patches
only the pinned plugin in this kit's own `node_modules`. Real sensor values and
firmware are untouched. Existing helpers are reused only when their templates,
units and device association match exactly. An existing unmanaged bridge config
is never overwritten. Private state defaults to `~/.terrestream-alexa`; use
`--home /your/private/path` consistently on all commands to choose another path.

## 3. Start and pair

```sh
node bridge.mjs register
node bridge.mjs start
```

On a host with several network interfaces, pass the actual LAN interface, for
example `node bridge.mjs start --interface en1` on the tested Mac. The bridge
frontend is at **http://127.0.0.1:8287** on that host; it is bound to loopback.
For a headless host, use an SSH tunnel to view that frontend. The Matter service
itself advertises on the LAN. Leave the foreground process running and keep the
host awake. Allow roughly 35 seconds for initial readings.

1. Ask the Echo to check for software updates and let it finish.
2. In the iPhone Alexa app, use **Devices → + → Add Device**. Select the discovered
   Matterbridge hub when available. Otherwise find **Matter** in the shortcuts
   or **Other** category, then scan the bridge's QR code.
3. The bridge is not Matter certified, and Alexa may show that warning. Proceed
   only if you want to use this optional self-hosted bridge.
4. Wait for **Terrestream** to appear. Check its device summary and View Dashboard
   against the table above. Keep the bridge pairing once successful.

The top-row Matter shortcut failed during our test while the automatically
discovered hub route succeeded. Updating the Echo and the later device
registration changes both preceded successful sensor display; a single cause
was not isolated. If a newly added VOC capability remains absent, see below.

## VOC and IAQ interpretation

Alexa displayed a received TVOC concentration of 288 µg/m³ as **288 VOCs index**
on a **0–100** chart. The optional adapter corrects this observed presentation
using a separate dimensionless Terrestream score:

| Estimated TVOC (WELL), µg/m³ | Alexa compatibility score |
|---|---|
| 0 | 0 |
| 290 | 25 |
| 660 | 65 |
| 3300 or more | 100 |

The score interpolates linearly between anchors. It is **not Amazon's proprietary
sensor algorithm**. HA retains the actual concentration and exposes a separate
unitless helper. The adapter deliberately sends the helper through the Matter
TVOC field, which still declares µg/m³ on the wire. This is a **nonstandard
Alexa-only display workaround**; do not pair this bridge with Apple Home,
Google Home or another controller. Use a separate unmodified bridge for them.
Missing/invalid helper values become unavailable, and its Matter numeric value
is cleared rather than replaced with zero.

IAQ uses the sensor's particulate AQI and its exact inclusive firmware cut
points: 50, 100, 150, 200 and 300. These map in order to Matter's Good, Fair,
Moderate, Poor, Very Poor and Extremely Poor categories. The wording differs
from the firmware's EPA labels. This is not a new combined gas-and-particle index.

## Maintenance and troubleshooting

- **Updates:** versions are pinned. Do not update Matterbridge or its HA plugin
  independently, or use its automatic update control for this kit. The launcher
  refuses to start if dependencies, patch hashes or sensor selection change.
  `npm ci` removes the installed adapter; do not run it over a configured kit.
- **Restart:** use Ctrl-C or your service manager to stop gracefully, then repeat
  `node bridge.mjs start`. The bridge home retains its Matter identity and pairing.
  Set up a service on your always-on host if you need automatic startup; this
  kit's foreground command is not itself an installed boot service.
- **Upgrade from our earlier lab:** retain its identity/configuration rather
  than following a fresh-home installation. A public 0.1.1 HA installation alone
  does not have this companion. HACS updates the integration, not bridge files.
- **TVOC still absent:** confirm both helpers and the WELL estimate are live in HA,
  and check the bridge's Terrestream endpoint. In our test, refreshing sensor
  registrations with TVOC already included made it appear. Back up the bridge
  home before using Matterbridge's **Unregister devices** action and restarting.
  That action affects every endpoint on this dedicated bridge; it is not the
  same as a factory reset. Rediscovery and restoring room/routine assignments may
  be necessary. Do not erase pairing storage as a first troubleshooting step.
- **Stale/unreachable:** HA marks expired source readings unavailable, but Alexa
  or the bridge may retain a recent displayed value during a connection outage.
  The initial outage trial still showed reachable endpoints after 15 seconds.
  A displayed Alexa value alone is not proof of a fresh sensor reading.
- **Restore original VOC transport:** stop the companion, run
  `node bridge.mjs restore-voc`, then start it again. The true concentration is
  exported again, so Alexa's index chart can again be misleading. HA helpers and
  Matter pairing remain intact. To re-enable, retain the private home and contact
  support rather than deleting it or re-running initial setup over it.

For support, include HA, bridge/plugin and Echo versions, which app screen is
missing a reading, and redacted errors. Never include tokens, pairing QR codes,
HA storage or the private bridge home. [Report an issue](https://github.com/terrestream/terrestream/issues).

## Developer verification

```sh
.venv/bin/python -m unittest discover -s . -p 'test_*.py'
npm test
```

Run tests in a fresh dependency installation. Runtime tests patch an isolated
copy of the upstream module and exercise unavailable/recovery behavior in
memory; they do not write synthetic measurements to a physical device or Alexa.
The physical trial and remaining limits are recorded in
[release status](https://github.com/terrestream/terrestream/blob/v0.1.2/docs/release-status.md).
