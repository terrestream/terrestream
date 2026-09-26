"""Publication packages must not accidentally include private runtime material."""

import io
import shutil
import tarfile

import pytest

from tools.package_release import (
    FILES,
    ROOT,
    normalize_sdist,
    selected_files,
    validate_licenses,
)


def test_public_archive_excludes_runtime_evidence_and_keys(tmp_path):
    for name in FILES:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    secret = tmp_path / "evidence" / "auth.json"
    secret.parent.mkdir()
    secret.write_text('{"access_token":"not-a-real-token"}')
    key = tmp_path / "src" / "unexpected.key"
    key.parent.mkdir()
    key.write_text("not-a-real-key")
    assert secret not in selected_files(tmp_path)
    assert key not in selected_files(tmp_path)


def test_public_archive_rejects_symlink_to_private_file(tmp_path):
    for name in FILES:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    folder = tmp_path / "src"
    folder.mkdir()
    (folder / "unexpected.json").symlink_to(tmp_path / "README.md")
    with pytest.raises(ValueError, match="Symlink"):
        selected_files(tmp_path)


def test_public_archive_excludes_generated_package_metadata(tmp_path):
    for name in FILES:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    generated = tmp_path / "src" / "terrestream_local.egg-info" / "SOURCES.txt"
    generated.parent.mkdir(parents=True)
    generated.write_text("private-build-input.txt\n")
    assert generated not in selected_files(tmp_path)


def test_public_archive_excludes_internal_and_unlisted_support_files(tmp_path):
    for name in FILES:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    private_files = [
        tmp_path / "internal" / "qualification" / "soak.py",
        tmp_path / "internal" / "reviews" / "inventory.md",
        tmp_path / "docs" / "private-notes.md",
        tmp_path / "tools" / "internal-helper.py",
    ]
    for path in private_files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("internal review material\n")
    assert set(private_files).isdisjoint(selected_files(tmp_path))


def test_public_archive_preserves_project_and_upstream_licenses():
    validate_licenses(selected_files())


@pytest.mark.parametrize(
    "omitted",
    [
        "NOTICE",
        "custom_components/terrestream_local/LICENSE",
        "src/terrestream_local/_espressif/LICENSE",
    ],
)
def test_release_rejects_missing_distribution_license(omitted):
    files = [p for p in selected_files() if p != ROOT / omitted]
    with pytest.raises(ValueError, match="Missing distribution notice"):
        validate_licenses(files)


def test_release_rejects_hidden_source_material(tmp_path):
    source = tmp_path / "src"
    source.mkdir()
    (source / ".private.json").write_text("{}")
    with pytest.raises(ValueError, match="Unexpected hidden file"):
        selected_files(tmp_path)


def test_source_distribution_removes_build_identity_without_changing_files(tmp_path):
    archive = tmp_path / "client.tar.gz"
    payload = b"public source contents\n"
    with tarfile.open(archive, "w:gz") as output:
        member = tarfile.TarInfo("client/src/client.py")
        member.size = len(payload)
        member.uid, member.gid = 123, 456
        member.uname, member.gname = "private-builder", "private-group"
        member.mtime = 123456789
        member.pax_headers = {"mtime": "123456789.12", "comment": "private metadata"}
        output.addfile(member, io.BytesIO(payload))
    normalize_sdist(archive)
    with tarfile.open(archive) as output:
        member = output.getmember("client/src/client.py")
        assert output.extractfile(member).read() == payload
        assert (member.uid, member.gid, member.mtime) == (0, 0, 0)
        assert (member.uname, member.gname, member.pax_headers) == ("", "", {})
    normalized = archive.read_bytes()
    assert normalized[4:8] == b"\x00" * 4
    normalize_sdist(archive)
    assert archive.read_bytes() == normalized


def test_source_distribution_rejects_links_without_rewriting_archive(tmp_path):
    archive = tmp_path / "client.tar.gz"
    with tarfile.open(archive, "w:gz") as output:
        member = tarfile.TarInfo("client/link")
        member.type = tarfile.SYMTYPE
        member.linkname = "/private/file"
        output.addfile(member)
    original = archive.read_bytes()
    with pytest.raises(ValueError, match="Unsafe source distribution member"):
        normalize_sdist(archive)
    assert archive.read_bytes() == original
