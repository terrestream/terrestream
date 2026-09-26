# Espressif provisioning code

Derived from ESP-IDF v5.5.4 `tools/esp_prov/security/{security,security2,srp6a}.py`,
`tools/esp_prov/utils/convenience.py`, and `components/protocomm/python/*_pb2.py`.
Upstream copyright: Espressif Systems (Shanghai) CO LTD. License: Apache-2.0;
see LICENSE in this directory.

Local adaptations use package-relative imports and Python typing annotations.
The package initializers expose only the modules needed for Security 2 pairing.
Security 2 patch version 1 is required for per-message nonces. The generated
protocol modules retain the full upstream schema and dependencies.

Source: https://github.com/espressif/esp-idf/tree/v5.5.4/tools/esp_prov
