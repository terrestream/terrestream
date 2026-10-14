// ALEXA-ONLY WORKAROUND: Alexa treats the Matter TVOC number as its 0–100 VOC index.
// This is deliberately nonstandard on the wire (the cluster still says ug/m3).
// Never enable this on a bridge shared with another Matter ecosystem.
// HA's real TVOC entity and its dimensionless helper are never modified here.
export const HELPER = 'sensor.terrestream_alexa_voc_index';

export function isAlexaVocEntity(entityId, enabled = process.env.TERRESTREAM_ALEXA_VOC_COMPAT === '1') {
  return enabled && entityId === HELPER;
}

export function adaptAlexaVocState(entityId, state, enabled = process.env.TERRESTREAM_ALEXA_VOC_COMPAT === '1') {
  if (!state || !isAlexaVocEntity(entityId, enabled)) return state;
  const attributes = state.attributes ?? {};
  const raw = state.state;
  const number = (typeof raw === 'number' || (typeof raw === 'string' && raw.trim() !== '')) ? Number(raw) : NaN;
  const valid = Number.isFinite(number) && number >= 0 && number <= 100 &&
    attributes.state_class === 'measurement' && !attributes.device_class && !attributes.unit_of_measurement;
  // Preserve unavailable topology on startup, while keeping its value missing.
  const { restored: _restored, ...copied } = attributes;
  return {
    ...state,
    state: valid ? String(number) : 'unavailable',
    attributes: { ...copied, state_class: 'measurement', device_class: 'volatile_organic_compounds', unit_of_measurement: 'µg/m³' },
  };
}
