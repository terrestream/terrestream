# Maintaining and publishing Terrestream Local

Organization: `terrestream` (Aerodyne Inc.). Contact: `support@terrestream.com`.
Individual maintainer and organization owner: `@Xynergi`. Repository: [terrestream/terrestream](https://github.com/terrestream/terrestream).

## Build and verify

Use Python 3.14 in a dedicated environment:

```sh
python -m pip install -e . -r requirements-test.txt
python tools/verify.py
python -m build
python tools/package_release.py
python -m twine check dist/*.whl dist/*.tar.gz
```

The source ZIP contains the files selected by `tools/package_release.py`. The
custom ZIP contains the installable component, which requires the pinned client
package on PyPI. `dist/release-manifest.json` records source and archive hashes.
Credentials, runtime evidence, firmware binaries and build metadata do not belong
in the source ZIP.
The packaging step also removes local account and timestamp metadata from the
Python source distribution. Publish only the distributions after that step.

## Release sequence

1. Complete hardware and local installation tests. Record the firmware build,
   client version, integration revision and HA version; see
   [RELEASE_STATUS.md](release-status.md) for outstanding tests.
2. Review and publish the source archive to the public repository. Enable issues,
   add a repository description and topics, and enable private vulnerability reporting
   under GitHub **Settings → Security → Advanced Security**. Confirm the reporting
   route in SECURITY.md works. HACS and hassfest must pass without ignored checks.
3. Configure the `pypi` GitHub environment with release review and restricted tags.
   Set up PyPI Trusted Publishing for `terrestream-local`, owner `terrestream`,
   repository `terrestream`, workflow `publish-pypi.yml`, environment `pypi`.
4. Push the reviewed `client-v<version>` tag. The tag-push workflow verifies the
   version, runs tests, builds the client and publishes it to PyPI through OIDC after
   environment approval. Do not create a GitHub Release for a client tag: HACS
   treats repository releases as integration updates. The source tag and public CI
   run provide the client's release provenance.
5. Install the published dependency in clean HA OS and Linux Container instances.
   Verify physical pairing, controls, restart and removal.
6. Check that the integration manifest version matches `v<version>`, its pinned
   client is available on PyPI, and HACS/hassfest pass for the same commit. Create
   the integration GitHub Release with its release notes, required firmware version,
   `terrestream-ha-<version>-custom.zip` and `SHA256SUMS`. Only integration versions
   receive GitHub Releases. HACS custom-repository installation uses
   `terrestream/terrestream`; default-list inclusion requires a separate review.
7. Distribute the firmware before submitting the Core contribution.

## Home Assistant Core contribution

The initial contribution covers sensors and physical-code setup at Bronze. Keep
the client as a separate PyPI dependency. Use Core's integration and test paths,
remove custom-only manifest fields and local brand assets, and use Core's
documentation URL. Confirm the final domain with reviewers because an older cloud
integration already uses the Terrestream name.

Retain identity verification, certificate pinning, freshness, controller-lease
release and failure handling. Submit additional platforms, profile actions,
migration, diagnostics, reauthentication and reconfiguration in follow-up PRs.
Run the reduced contribution's tests in Core's test environment.

Submit matching sensor documentation and a separate brands PR. The local quality
checklist records implementation status; it does not confer an awarded HA quality
tier or Works with Home Assistant certification.

## References

- [Core contributions](https://developers.home-assistant.io/docs/core/integration/contributing_to_core/)
- [Dependency transparency](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/dependency-transparency/)
- [Integration ownership](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/integration-owner/)
- [Brand images](https://developers.home-assistant.io/docs/core/integration/brand_images/)
- [HACS publishing](https://www.hacs.xyz/docs/publish/integration/)
- [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/)
