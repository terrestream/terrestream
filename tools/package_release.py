"""Build source and manual-install archives from the release file list."""

import gzip
import hashlib
import io
import json
import tarfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    ".gitignore",
    "MANIFEST.in",
    "LICENSE",
    "NOTICE",
    "THIRD_PARTY_NOTICES.md",
    "README.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "docs/client.md",
    "docs/protocol.md",
    "docs/migration.md",
    "docs/release-status.md",
    "docs/maintaining.md",
    "docs/licensing.md",
    "tools/package_release.py",
    "tools/pair_check.py",
    "tools/verify.py",
    "pyproject.toml",
    "requirements-test.txt",
    "hacs.json",
)
DIRECTORIES = ("src", "custom_components", "tests", "blueprints", ".github")
SUFFIXES = {
    ".py",
    ".typed",
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".txt",
    ".png",
}


def selected_files(root=ROOT):
    selected = [root / name for name in FILES]
    for folder in DIRECTORIES:
        for path in (root / folder).rglob("*"):
            if path.is_symlink():
                raise ValueError("Symlink in public source")
            if any(
                part.startswith(".") and part != ".github"
                for part in path.relative_to(root).parts
            ):
                raise ValueError("Unexpected hidden file in public source")
            if not path.is_file() or any(
                part == "__pycache__" or part.endswith(".egg-info")
                for part in path.parts
            ):
                continue
            if path.suffix in SUFFIXES or path.name in {
                "LICENSE",
                "NOTICE",
                "CODEOWNERS",
            }:
                selected.append(path)
    for path in selected:
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Missing or unsafe release input: {path.name}")
    return sorted(selected)


def validate_licenses(files, root=ROOT):
    """Keep project and upstream license notices in each distribution."""
    selected = set(files)
    required = (
        "LICENSE",
        "NOTICE",
        "THIRD_PARTY_NOTICES.md",
        "custom_components/terrestream_local/LICENSE",
        "custom_components/terrestream_local/NOTICE",
        "src/terrestream_local/_espressif/LICENSE",
        "src/terrestream_local/_espressif/UPSTREAM.md",
    )
    for name in required:
        if root / name not in selected:
            raise ValueError(f"Missing distribution notice: {name}")
    if (root / "LICENSE").read_bytes() != (
        root / "custom_components/terrestream_local/LICENSE"
    ).read_bytes():
        raise ValueError("Component license differs from project license")


def archive(path, files):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for file in files:
            entry = zipfile.ZipInfo(
                file.relative_to(ROOT).as_posix(), (2026, 9, 25, 0, 0, 0)
            )
            entry.external_attr = 0o100644 << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            output.writestr(entry, file.read_bytes())


def normalize_sdist(path):
    """Remove local account names, IDs and timestamps from archive metadata."""
    output = io.BytesIO()
    with (
        tarfile.open(path, "r:gz") as source,
        gzip.GzipFile(fileobj=output, mode="wb", filename="", mtime=0) as compressed,
        tarfile.open(fileobj=compressed, mode="w") as target,
    ):
        for member in source.getmembers():
            if (
                not (member.isfile() or member.isdir())
                or Path(member.name).is_absolute()
                or ".." in Path(member.name).parts
            ):
                raise ValueError("Unsafe source distribution member")
            contents = source.extractfile(member) if member.isfile() else None
            member.uid = member.gid = 0
            member.uname = member.gname = ""
            member.mtime = 0
            member.pax_headers = {}
            target.addfile(member, contents)
    path.write_bytes(output.getvalue())


def main():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    manifest = json.loads(
        (ROOT / "custom_components/terrestream_local/manifest.json").read_text()
    )
    assert manifest["requirements"] == [f"terrestream-local=={project['version']}"]
    assert manifest["codeowners"] == ["@Xynergi"]
    files = selected_files()
    validate_licenses(files)
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    normalize_sdist(dist / f"terrestream_local-{project['version']}.tar.gz")
    source = dist / f"terrestream-ha-{manifest['version']}-source.zip"
    install = dist / f"terrestream-ha-{manifest['version']}-custom.zip"
    archive(source, files)
    archive(install, [p for p in files if p.is_relative_to(ROOT / "custom_components")])
    hashes = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (
            source,
            install,
            dist / f"terrestream_local-{project['version']}-py3-none-any.whl",
            dist / f"terrestream_local-{project['version']}.tar.gz",
        )
    }
    receipt = {
        "version": manifest["version"],
        "published": False,
        "release_qualified": False,
        "archives_sha256": hashes,
        "source_files_sha256": {
            p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in files
        },
    }
    (dist / "release-manifest.json").write_text(json.dumps(receipt, indent=2) + "\n")
    (dist / "SHA256SUMS").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in hashes.items())
    )
    print(f"Prepared {len(files)} allowlisted files; no publication performed.")


if __name__ == "__main__":
    main()
