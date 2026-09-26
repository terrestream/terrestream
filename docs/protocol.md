# Local protocol 1 — candidate contract

This protocol is under qualification for firmware 4.1.0. It is not frozen for
production; wire changes require corresponding client and firmware updates.

## Trust and pairing

The device exposes a temporary HTTP service on port 6054 only during a physical
120-second pairing window. `POST /pair` carries Espressif protocomm Security 2
messages (SRP6a, 3072-bit group, SHA-512, username `terrestream`, eight decimal code
digits). The code uses unbiased random generation. Up to ten handshake messages
are allowed per window; a new window requires another physical action.

`POST /bootstrap` carries the exact plaintext `bootstrap` under the established
Security 2 AES-GCM session. Patch version 1 nonce sequencing is required. The
response, also encrypted, carries `protocol`, UUID, TLS port, SHA-256 certificate
fingerprint and a fresh 256-bit bearer token. Neither the code nor credentials are
advertised in mDNS or written to logs. The Python wrapper rejects incorrect phase,
status, key/salt/proof/nonce lengths before invoking upstream pairing operations.

The candidate client verifies the bootstrap certificate pin over TLS before saving
credentials. HA saves the entry, then sends `confirm`; the device persists its
single versioned pairing record as an NVS blob, commits and reads it back. A flow
cancelled before entry creation leaves an expiring candidate only. A power loss
before confirmation requires re-pairing; a lost confirm response is recoverable
because HA already holds the credentials. Physical disconnect erases the record;
subsequent pairing creates a new key, certificate and token.

Peer authentication uses the exact paired certificate fingerprint, independent of
DNS name and wall-clock validity. The corresponding private key authenticates TLS.
This policy applies only to this local client; vendor HTTPS verification and real
NTP requirements for cloud signatures are not modified. Production storage and
physical-extraction properties depend on the qualified secure device flavor.

## RPC and controller ownership

Steady-state API: `POST https://DEVICE:6053/rpc`, bearer authorization, JSON bodies.
No redirects are followed. Input is bounded below 2048 bytes, response below 12288
bytes; Python bounds reads to 16384 bytes. Firmware uses one queued command slot,
a two-second handler deadline and two TLS sockets with idle eviction. Main-loop
execution owns setting/UI/maintenance actions. Timed-out queued work is cancelled;
already executing work retains its slot until completion.

`identity` and `confirm` authenticate without claiming or renewing control. An
identity response includes protocol, UUID and `paired`. Reconfiguration/discovery
must prove this identity under the existing pin before saving a new endpoint.
The advertised `_terrestream._tcp.local.` service includes UUID, protocol and model;
discovery text alone is never authority to replace credentials or change an endpoint.

A controller generates a fresh random 128-bit runtime ID, not stored in its HA
backup. `snapshot` obtains a random device session and boot nonce plus monotonic
`uptime_ms`. The controller supplies its preceding session/boot on later polls.
The lease renews for 60 seconds. A different controller is refused until expiry;
a displaced session from the same boot is refused even after that expiry, so two
live instances cannot keep reclaiming ownership. A displaced client latches the
conflict and requires an explicit reload after the duplicate is stopped. A new
HA process may retry its initial claim after a crash lease. Device reboot resets
lease/session generation. `release` ends an orderly controller session.

Executable methods require controller, boot/session, increasing uint32 request ID
and `expires_ms` in the device monotonic time domain. The accepted future window
is at most ten seconds; the client uses five seconds and a snapshot no older than
two seconds. An identical retry retains the entire envelope. The most recent
completed result is cached; older IDs are rejected without execution. Session
changes reset client sequence and invalidate old commands. This is bounded RAM
at-most-once execution within a session, not a persistent multi-request job queue.

Responses contain `ok`; executed commands also return their request ID and status.
The client rejects uncorrelated/unknown success results. Unknown operation fields
are rejected, including URL/artifact fields on update requests. No command input
is retained across boots. Unsupported protocol major versions fail validation.

## Measurements and settings

A snapshot contains identity, versions, boot/session, monotonic uptime,
`capabilities`, `settings`, `settings_revision`, `measurements`, `maintenance`,
`update`, cloud-policy flags and non-identifying resource health counters.
Each measurement has availability, nullable value, acquisition sequence, nullable
monotonic age, remaining validity and a reason. All readings and metadata are copied
under the sensor mutex; source timestamps change only after successful acquisition.

| Key | Native unit / interpretation |
|---|---|
| `co2` | ppm |
| `pm1`, `pm25`, `pm4`, `pm10` | µg/m³ |
| `temperature`, `humidity` | °C, % |
| `pressure`, `illuminance` | hPa, lx |
| `voc_index`, `nox_index` | Sensor indices, no physical concentration unit |
| `computed_epa_aqi` | Instantaneous particulate proxy, EPA 2024 breakpoints; independent of display index mode |
| `estimated_tvoc_well`, `estimated_tvoc_reset` | Separate optional VOC-index estimates in µg/m³; only the selected method is available |

Air/pressure validity budget is 60 seconds; light is 20 seconds. The client counts
request time against the remaining budget and the HA entity schedules expiry
independently of future polls. These budgets remain subject to qualification. Warm-up,
sentinels, non-finite values, cleaning and stale sources do not become zero.

`set` accepts one key/value plus the observed `expected_revision`. The device
recomputes settings state before comparing revisions and reuses existing setters,
under the same recursive preference guard used by BLE changes. The complete durable
preference blob is committed and read back before success. `import_preferences`
accepts a complete allowlisted schema-1 profile under the same revision and storage
guards; failure restores the previous in-memory state. `preferences_profile=1`
advertises this support. Legacy per-key mirrors remain for compatibility, but an
interrupted downgrade to old firmware does not inherit the new blob atomicity.

| Keys | Accepted values |
|---|---|
| `dark_mode`, `fahrenheit`, `time_24h`, `auto_brightness`, `quiet_hours`, `ui_sounds`, `notification_sounds` | Integer 0 or 1 |
| `display_brightness`, `ring_brightness`, `volume` | 10–255, 0–64, 0–10 |
| `quiet_display`, `quiet_ring`, `quiet_volume` | 1–255, 0–64, 0–10 |
| `quiet_start`, `quiet_end` | Minutes since local midnight, 0–1439 |
| `locale` | 0 English, 1 French Canada; existing convention-default side effects apply |
| `index_mode` | 0 EPA AQI display, 1 AQHI+ display |
| `voc_mode` | 0 index, 1 WELL estimate, 2 RESET estimate |
| `timezone` | Device-supported IANA zone, validated by the existing timezone registry |

`time` takes epoch seconds and uncertainty in milliseconds. A five-minute volatile
HA presentation anchor supports display/quiet scheduling; HA refreshes it every
minute. It never sets the system clock, records an SNTP event or authorizes cloud
signatures. When the anchor expires, only a genuine current-boot NTP sync is a
fallback. Pairing/session resets clear the anchor. Scheduled fan-cleaning time
retains its existing real-NTP policy.

## Maintenance and recovery

`fan_clean` starts the existing nonblocking cleaning operation. Its correlated
result is accepted; snapshots show running and terminal success/failure using the
existing completion timestamp. The independent light/pressure samples continue.

`check_update` and `install_update` queue the existing approved server flows after
sending acceptance. Local TLS drains before server TLS allocates. A checked catalog
with no update differs from an unknown catalog. While the main loop runs the
existing synchronous update flow, HA is unavailable; update progress is not reported.
A successful install reboots and is reconciled through the returned version.
A durable `update_operation` record survives reboot and reports accepted,
awaiting-validation, succeeded, rolled-back, or interrupted outcomes. Physical
power-loss and retail rollback qualification remain required.

`unpair` queues pairing revocation after replying. It does not reset user settings,
Bluetooth, Wi-Fi, manufacturing identity or cloud ownership. Factory reset invokes
local revocation in addition to its existing ownership-receipt-safe workflow.
BLE onboarding, portal and update startup suspend the local listener; native
polling resumes when those resource gates clear. User-managed MQTT takes priority
if enabled; its settings are preserved. Continuous coexistence is not yet qualified.

`cloud_policy` is `cloud_enabled` or `local_only`; `local_only_supported=true`.
The explicit `cloud_policy` command durably stores the policy and serializes with
the complete cloud-send cycle. Opt-out purges queued measurements, including an
immediate off/on transition. Corrupt policy storage fails closed.

In local-only mode, firmware may still contact Terrestream to verify update
health. This exchange excludes environmental measurements. Firmware updates
continue to use the Terrestream server; HA makes no vendor-cloud requests.
