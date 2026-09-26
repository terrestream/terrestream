# Third-party notices

## Espressif ESP-IDF provisioning code

Files under `src/terrestream_local/_espressif/` derive from Espressif ESP-IDF
v5.5.4 provisioning and protocomm Python code, with local package and typing
adaptations. Existing Espressif copyright notices are retained verbatim. Aerodyne
claims only its original contributions and modifications, not the upstream code.

- Upstream owner: Espressif Systems (Shanghai) CO LTD.
- Upstream license: Apache License, Version 2.0.
- License copy: `src/terrestream_local/_espressif/LICENSE`.
- Source and adaptation details: `src/terrestream_local/_espressif/UPSTREAM.md`.
- [Provisioning source](https://github.com/espressif/esp-idf/tree/v5.5.4/tools/esp_prov).
- [Protocol source](https://github.com/espressif/esp-idf/tree/v5.5.4/components/protocomm/python).

The client distributions include this upstream license and modification provenance.
The protobuf-generated files retain their generation headers and contents.

## Separately installed dependencies

The Python client depends on aiohttp, cryptography and protobuf. They are installed
as separate packages, not copied into this repository. Their own license files and
notices accompany their distributions; this project's Aerodyne notice does not
claim ownership of those dependencies. Development and Home Assistant dependencies
likewise retain their respective terms.

## Other names and license text

Home Assistant is a trademark of the Open Home Foundation. References identify
compatibility and do not imply certification or endorsement. Other third-party
names and marks remain with their respective owners. The Apache license text is
reproduced unchanged and is not claimed as original Aerodyne-authored text.
