"""Narrow patch for the pinned matterbridge-hass 1.5.0 build."""


def patched_module(original):
    text = original.decode()
    assert "terrestream-alexa-voc.mjs" not in text, "Unexpected existing patch"
    old = "const hassState = this.ha.hassStates.get(entity.entity_id);"
    assert text.count(old) == 3, "Plugin startup code changed"
    text = text.replace(
        old,
        "const hassState = adaptAlexaVocState(entity.entity_id, this.ha.hassStates.get(entity.entity_id));",
    )
    old = "    async updateHandler(deviceId, entityId, old_state, new_state) {"
    assert text.count(old) == 1, "Plugin update handler changed"
    text = text.replace(
        old,
        old
        + "\n        old_state = adaptAlexaVocState(entityId, old_state);\n        new_state = adaptAlexaVocState(entityId, new_state);",
    )
    old = "        if (old_state.state !== 'unavailable' && new_state.state === 'unavailable') {"
    assert text.count(old) == 1, "Plugin availability handling changed"
    text = text.replace(
        old,
        """        // The grouped device may be reachable through a sibling; clear this stale metric itself.
        if (isAlexaVocEntity(entityId) && new_state.state === 'unavailable') {
            await endpoint.setAttribute(1070, 'measuredValue', null, endpoint.log);
        }
"""
        + old,
    )
    return (
        "import { adaptAlexaVocState, isAlexaVocEntity } from './terrestream-alexa-voc.mjs';\n"
        + text
    ).encode()
