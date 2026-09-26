# Contributing

Report reproducible bugs through the issue form. Include versions and redacted
diagnostics, and check existing issues first. Follow [SECURITY.md](SECURITY.md)
for vulnerabilities or sensitive reports.

Discuss substantial changes in an issue before implementation. Keep pull requests
focused and describe the user-visible behavior, validation performed and any
compatibility changes.

## Development

Use Python 3.14 and work from the repository root:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -e . -r requirements-test.txt
python tools/verify.py
```

The verification script runs lint, formatting, typing and tests, and enforces
more than 95% combined statement and branch coverage per integration module.
GitHub also runs hassfest, HACS validation and client tests on Python 3.13/3.14.

- Keep device communication in `src/terrestream_local/` and HA behavior in
  `custom_components/terrestream_local/`.
- Add tests for changed behavior. Preserve missing/stale readings as unavailable,
  certificate pinning, pairing confirmation and command retry semantics.
- Keep `strings.json` and the supplied translations consistent when changing UI text.
- Use synthetic device identities and credentials in tests. Do not commit runtime
  records, firmware images, private keys or HA backups.
- Preserve upstream copyright and license notices in vendored code. Keep its
  modifications documented in `_espressif/UPSTREAM.md`.

See [protocol](docs/protocol.md), [client usage](docs/client.md) and
[maintaining the project](docs/maintaining.md) for further details. Package and
release instructions are for maintainers; a contribution does not publish a release.

Contributions are distributed under this repository's Apache 2.0 license.
