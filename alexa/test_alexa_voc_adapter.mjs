import assert from 'node:assert/strict';
import { test } from 'node:test';
import { adaptAlexaVocState, HELPER, isAlexaVocEntity } from './alexa_voc_adapter.mjs';

const state = (value, attributes = {}) => ({ entity_id: HELPER, state: value, attributes: { state_class: 'measurement', ...attributes } });

test('opt-in exact helper only; physical TVOC and CO2 pass through untouched', () => {
  const source = state('288', { device_class: 'volatile_organic_compounds', unit_of_measurement: 'µg/m³' });
  for (const id of ['sensor.terrestream_r500_estimated_tvoc_well', 'sensor.terrestream_r500_carbon_dioxide', HELPER + '_other']) {
    assert.strictEqual(adaptAlexaVocState(id, source, true), source);
  }
  assert.strictEqual(adaptAlexaVocState(HELPER, source, false), source);
  assert.equal(isAlexaVocEntity(HELPER, false), false);
});

test('valid score becomes an isolated wire copy, with no HA state mutation', () => {
  const input = state('24.8');
  Object.freeze(input.attributes); Object.freeze(input);
  const output = adaptAlexaVocState(HELPER, input, true);
  assert.equal(output.state, '24.8');
  assert.equal(output.attributes.device_class, 'volatile_organic_compounds');
  assert.equal(output.attributes.unit_of_measurement, 'µg/m³');
  assert.equal(input.attributes.device_class, undefined);
  assert.notStrictEqual(output.attributes, input.attributes);
});

test('unavailable, invalid and mismatched quantities never become zero', () => {
  for (const value of ['unknown', 'unavailable', '', ' ', 'NaN', 'Infinity', '-1', '100.01', null, true]) {
    assert.equal(adaptAlexaVocState(HELPER, state(value), true).state, 'unavailable', String(value));
  }
  for (const attrs of [{ unit_of_measurement: 'µg/m³' }, { device_class: 'aqi' }, { state_class: undefined }]) {
    assert.equal(adaptAlexaVocState(HELPER, state('24', attrs), true).state, 'unavailable');
  }
});

test('missing startup state stays missing; restored unavailable helper keeps topology', () => {
  assert.equal(adaptAlexaVocState(HELPER, undefined, true), undefined);
  const output = adaptAlexaVocState(HELPER, state('unavailable', { restored: true }), true);
  assert.equal(output.state, 'unavailable');
  assert.equal(output.attributes.restored, undefined);
  for (const value of ['0', '25', '65', '100']) assert.equal(adaptAlexaVocState(HELPER, state(value), true).state, value);
});
