from __future__ import annotations

import sys
from typing import Final

MINIMUM_SUPPORTED_PYTHON: Final = (3, 11)
MINIMUM_SUPPORTED_PYTHON_LABEL: Final = "3.11"


def ensure_supported_python() -> None:
    if sys.version_info >= MINIMUM_SUPPORTED_PYTHON:
        return
    current_version = ".".join(str(part) for part in sys.version_info[:3])
    print(
        "error: Research PDF Vault requires Python "
        f"{MINIMUM_SUPPORTED_PYTHON_LABEL}+; current interpreter is "
        f"{current_version}. Use a Python 3.11+ interpreter, for example "
        "/opt/homebrew/bin/python3 on macOS when available.",
        file=sys.stderr,
    )
    raise SystemExit(2)
