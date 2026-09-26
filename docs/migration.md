# Preserve existing measurement history

Migration is optional. Back up Home Assistant first. Do not delete existing
entities or recorder statistics. Only same-device, same-meaning measurements with
compatible units/statistics move. Entity IDs, names, entity areas, disabled states,
and recorder statistic IDs stay intact. Website Pro insights are not migrated.

## From MQTT discovery

1. Record the existing R500 measurement entities you want to keep. Disable those
   entities in their HA settings and reload MQTT so they are no longer loaded.
   Keep the entities in HA's registry; do not disable unrelated MQTT devices.
2. Disable the device's user-managed MQTT connection before enabling its native
   HA pairing. Its stored broker preferences can remain saved for rollback.
3. Add Terrestream Local, pair on the physical R500, and select **Preserve MQTT
   measurement history** during setup.
4. Verify the original entity IDs now belong to Terrestream Local. Re-enable any
   migrated entities you disabled in step 1. Confirm dashboards and automations
   still reference the intended entities.
5. Remove obsolete retained discovery configuration messages for this R500 only,
   using your broker's administration tools after recording the exact old topics.
   Do not purge a broker-wide discovery prefix or remove another device's messages.
   Leaving retained messages can cause the old MQTT integration to recreate entries.

Matching uses the hardware UUID plus known legacy metric suffixes, never a room
name. CO₂, particulate measurements, temperature, humidity, pressure, illuminance,
VOC index and NOx index can migrate. Ambiguous computed/estimated index histories
are deliberately not relabeled as a different measurement.

## From the older Terrestream cloud component

1. In that integration, enable its **disable raw signals** option and reload it.
   Keep its cloud insights enabled if desired. Its current authenticated device
   roster must include this R500's UUID. This roster is used only for identity
   matching; the new integration does not copy its cloud token or contact the cloud.
2. Keep compatible old measurement entities in the registry but unloaded.
3. Add Terrestream Local and choose **Preserve cloud measurement history**.
4. Verify the original measurement entity IDs and history, then re-enable migrated
   entities as needed. Leave cloud insight entities with the older integration.

Only the migration from a previously configured cloud component needs that
component's authenticated roster. New local setup never requires a web account.

## If migration pauses

HA shows a setup error and a repair notice. Common causes are still-loaded old
entities, missing verified UUID, different units/state classes, or an existing
local entity that would create two histories for the same measurement. Resolve
the stated conflict, then reload the new integration. Choose which history to keep
manually where there are duplicates; the integration will not merge or erase it.

All candidates are checked before registry changes begin. If a registry operation
fails, earlier moves are rolled back to their previous integration. Successful
migration records completion, so reloading does not repeat the move. A single
shared old device area is carried over if the new device has no area; an existing
new-device area is preserved. Migration is covered by registry tests; testing
with existing physical MQTT/cloud installations remains pending.
