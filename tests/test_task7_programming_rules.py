from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
TASK7_SOURCE_FILES: Final = (
    ROOT / "plugins/research-pdf-vault/scripts/research_pdf_vault/metadata.py",
    ROOT / "plugins/research-pdf-vault/scripts/research_pdf_vault/fingerprint.py",
    ROOT / "plugins/research-pdf-vault/scripts/research_pdf_vault/identity.py",
    ROOT / "plugins/research-pdf-vault/scripts/research_pdf_vault/dedup.py",
    ROOT / "plugins/research-pdf-vault/scripts/research_pdf_vault/dedup_conflicts.py",
    ROOT / "plugins/research-pdf-vault/scripts/research_pdf_vault/dedup_models.py",
    ROOT / "plugins/research-pdf-vault/scripts/research_pdf_vault/scan_db.py",
)
MAX_PARAMETERS: Final = 3


def test_task7_python_when_signatures_checked_then_no_parameter_bloat() -> None:
    # Given
    violations: list[str] = []

    # When
    for source_file in TASK7_SOURCE_FILES:
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                parameter_count = _parameter_count(node.args)
                if parameter_count > MAX_PARAMETERS:
                    violations.append(
                        f"{source_file.relative_to(ROOT)}:"
                        f"{node.lineno}:{node.name}:{parameter_count}",
                    )

    # Then
    assert violations == []


def _parameter_count(arguments: ast.arguments) -> int:
    return sum(
        (
            len(arguments.posonlyargs),
            len(arguments.args),
            len(arguments.kwonlyargs),
            1 if arguments.vararg is not None else 0,
            1 if arguments.kwarg is not None else 0,
        ),
    )
