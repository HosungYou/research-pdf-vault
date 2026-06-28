from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Final

import pytest

ROOT: Final = Path(__file__).resolve().parents[1]
SYSTEM_PYTHON: Final = Path("/usr/bin/python3")
RPV_CLI: Final = ROOT / "plugins" / "research-pdf-vault" / "scripts" / "rpv.py"
MCP_SERVER: Final = (
    ROOT / "plugins" / "research-pdf-vault" / "scripts" / "mcp_server.py"
)
MINIMUM_SUPPORTED_VERSION: Final = (3, 11)


def test_rpv_entrypoint_when_python_is_too_old_then_reports_requirement() -> None:
    # Given
    if not _has_unsupported_system_python():
        pytest.skip("system python is not older than the plugin minimum")

    # When
    completed = subprocess.run(
        [str(SYSTEM_PYTHON), str(RPV_CLI), "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    # Then
    assert completed.returncode == 2
    assert "Research PDF Vault requires Python 3.11+" in completed.stderr
    assert "SyntaxError" not in completed.stderr


def test_mcp_entrypoint_when_python_is_too_old_then_reports_requirement() -> None:
    # Given
    if not _has_unsupported_system_python():
        pytest.skip("system python is not older than the plugin minimum")

    # When
    completed = subprocess.run(
        [str(SYSTEM_PYTHON), str(MCP_SERVER), "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    # Then
    assert completed.returncode == 2
    assert "Research PDF Vault requires Python 3.11+" in completed.stderr
    assert "SyntaxError" not in completed.stderr


def _has_unsupported_system_python() -> bool:
    if not SYSTEM_PYTHON.exists():
        return False
    completed = subprocess.run(
        [
            str(SYSTEM_PYTHON),
            "-c",
            "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return False
    major, minor = completed.stdout.strip().split(".", maxsplit=1)
    return (int(major), int(minor)) < MINIMUM_SUPPORTED_VERSION
