// Exercise the installed, patched plugin with in-memory endpoints only.
// No synthetic HA states or Matter attributes are sent to the live bridge.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import fs from 'node:fs';
import os from 'node:os';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { adaptAlexaVocState, HELPER } from './alexa_voc_adapter.mjs';

process.env.TERRESTREAM_ALEXA_VOC_COMPAT = '1';
const root = path.dirname(fileURLToPath(import.meta.url));
const dist = fs.mkdtempSync(path.join(root, 'node_modules/matterbridge-hass/test-copy-'));
fs.cpSync(path.join(root, 'node_modules/matterbridge-hass/dist'), dist, { recursive: true });
const python = process.env.PYTHON || 'python3';
execFileSync(python, ['-c', 'from pathlib import Path; from patch import patched_module; import sys; p=Path(sys.argv[1]); p.write_bytes(patched_module(p.read_bytes()))', path.join(dist, 'module.js')], { cwd: root });
fs.copyFileSync(path.join(root, 'alexa_voc_adapter.mjs'), path.join(dist, 'terrestream-alexa-voc.mjs'));
process.on('exit', () => fs.rmSync(dist, { recursive: true, force: true }));
const { HomeAssistantPlatform } = await import(pathToFileURL(path.join(dist, 'module.js')));
const { addSensorEntity } = await import(pathToFileURL(path.join(dist, 'sensor.entity.js')));
const log = { debug() {}, info() {} };
const state = (value, attributes = {}) => Object.freeze({ entity_id: HELPER, state: value,
  attributes: Object.freeze({ state_class: 'measurement', ...attributes }) });

function platform() {
  const writes = [];
  const device = { deviceName: 'Terrestream', log, getChildEndpointById: () => undefined,
    async setAttribute(cluster, attribute, value) { writes.push({ cluster: cluster.id ?? cluster, attribute, value }); } };
  const instance = Object.create(HomeAssistantPlatform.prototype);
  Object.assign(instance, { matterbridgeDevices: new Map([['physical', device]]),
    endpointNames: new Map([[HELPER, '']]), log, stateCache: { add() {}, remove() {} },
    batteryVoltageEntities: new Set(), airQualityRegex: undefined });
  return { instance, writes };
}

test('patched update handler clears TVOC on invalid/unavailable, then recovers', async () => {
  for (const missing of ['unavailable', 'unknown', 'NaN', '']) {
    const { instance, writes } = platform();
    const before = state('24.6447');
    const absent = state(missing);
    await instance.updateHandler('physical', HELPER, before, absent);
    assert.deepEqual(writes[0], { cluster: 1070, attribute: 'measuredValue', value: null });
    assert.equal(writes.at(-1).value, false);
    await instance.updateHandler('physical', HELPER, absent, before);
    assert.deepEqual(writes.at(-1), { cluster: 1070, attribute: 'measuredValue', value: 24.6447 });
    assert.equal(before.attributes.device_class, undefined);
    assert.equal(absent.state, missing);
  }
});

test('startup while unavailable keeps TVOC capability but no numeric value', async () => {
  const raw = state('unavailable', { restored: true });
  const adapted = adaptAlexaVocState(HELPER, raw, true);
  const clusters = [];
  const mutable = { addDeviceTypes() {}, addClusterServerIds(name, id) { clusters.push(id); }, setFriendlyName() {} };
  assert.equal(addSensorEntity({ log }, mutable, { entity_id: HELPER }, adapted, undefined, false), 'AirQuality');
  assert.deepEqual(clusters, [1070]);
  const { instance, writes } = platform();
  await instance.updateHandler('physical', HELPER, raw, raw);
  assert.deepEqual(writes[0], { cluster: 1070, attribute: 'measuredValue', value: null });
  assert.equal(raw.attributes.restored, true);
});

test('excluded canonical source cannot become a competing TVOC writer', async () => {
  const { instance, writes } = platform();
  const raw = state('288', { device_class: 'volatile_organic_compounds', unit_of_measurement: 'µg/m³' });
  await instance.updateHandler('physical', 'sensor.terrestream_r500_estimated_tvoc_well', raw, raw);
  assert.deepEqual(writes, []);
});
