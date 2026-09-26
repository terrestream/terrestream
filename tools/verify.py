"""Run the bounded HA checks and enforce per-module branch coverage."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
for command in [
    [
        sys.executable,
        "-m",
        "ruff",
        "check",
        "--exclude",
        "_espressif",
        "src",
        "custom_components",
        "tests",
        "tools",
    ],
    [
        sys.executable,
        "-m",
        "ruff",
        "format",
        "--check",
        "--exclude",
        "_espressif",
        "src",
        "custom_components",
        "tests",
        "tools",
    ],
    [sys.executable, "-m", "mypy"],
]:
    subprocess.run(command, check=True, timeout=60)
with tempfile.TemporaryDirectory(prefix="terrestream-ha-coverage-") as folder:
    report = Path(folder) / "coverage.json"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests",
            "-q",
            "--cov=custom_components.terrestream_local",
            "--cov-branch",
            "--cov-report=term-missing",
            f"--cov-report=json:{report}",
        ],
        check=True,
        timeout=60,
    )
    coverage = json.loads(report.read_text())
    for name, data in coverage["files"].items():
        if data["summary"]["percent_covered"] <= 95:
            raise SystemExit(f"{name}: coverage must exceed 95%")
print("All integration modules exceed 95% coverage.")
