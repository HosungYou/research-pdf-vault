from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Final

from _pytest.main import Session

ROOT: Final = Path(__file__).resolve().parent
GENERATED_CACHE_NAMES: Final = frozenset({"__pycache__", ".pytest_cache", ".ruff_cache"})

sys.dont_write_bytecode = True


def pytest_sessionfinish(session: Session, exitstatus: int) -> None:
    del session, exitstatus
    _remove_generated_caches()


def _remove_generated_caches() -> None:
    for current, dirnames, filenames in os.walk(ROOT):
        current_path = Path(current)
        for dirname in list(dirnames):
            if dirname in GENERATED_CACHE_NAMES:
                shutil.rmtree(current_path / dirname)
                dirnames.remove(dirname)
        for filename in filenames:
            if filename.endswith(".pyc"):
                (current_path / filename).unlink()
