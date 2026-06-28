from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
EXPECTED_DOCS: Final = (
    ROOT / "README.md",
    ROOT / "docs/architecture.md",
    ROOT / "docs/privacy-policy.md",
    ROOT / "docs/onedrive-sharepoint.md",
    ROOT / "docs/local-models.md",
    ROOT / "docs/dependency-policy.md",
    ROOT / "docs/licensing-copyright.md",
    ROOT / "docs/release-checklist.md",
)
PUBLIC_ROOTS: Final = (
    ROOT / "README.md",
    ROOT / "docs",
    ROOT / "fixtures",
    ROOT / "plugins/research-pdf-vault",
    ROOT / "schemas",
    ROOT / "tests",
)
REQUIRED_PUBLIC_TERMS: Final = (
    "Python 3.11+",
    "OCRmyPDF",
    "Tesseract",
    "SQLite",
    "FTS5",
    "local embedding",
    "offline/test mode",
)
SYNTHETIC_FIXTURE: Final = ROOT / "fixtures/public-hygiene/synthetic-metadata.json"
NEGATIVE_CONTROL: Final = ROOT / "fixtures/public-hygiene/negative-control.tmp.txt"


def test_public_docs_when_checked_then_required_release_topics_exist() -> None:
    # Given
    missing_docs = [path.relative_to(ROOT).as_posix() for path in EXPECTED_DOCS if not path.exists()]

    # When
    combined_docs = "\n".join(
        path.read_text(encoding="utf-8")
        for path in EXPECTED_DOCS
        if path.exists()
    )
    missing_terms = [term for term in REQUIRED_PUBLIC_TERMS if term not in combined_docs]

    # Then
    assert missing_docs == []
    assert missing_terms == []
    assert SYNTHETIC_FIXTURE.exists()


def test_public_surfaces_when_scanned_then_no_private_or_institutional_strings() -> None:
    # Given
    paths = list(_text_files(PUBLIC_ROOTS))

    # When
    findings = _scan(paths, _forbidden_patterns())

    # Then
    assert findings == []


def test_hygiene_scanner_when_private_path_fixture_exists_then_fails() -> None:
    # Given
    NEGATIVE_CONTROL.parent.mkdir(parents=True, exist_ok=True)
    private_path = "/".join(("", "Users", "hosung"))
    NEGATIVE_CONTROL.write_text(f"path = {private_path}\n", encoding="utf-8")

    try:
        # When
        findings = _scan([NEGATIVE_CONTROL], _forbidden_patterns())

        # Then
        assert findings == [f"{NEGATIVE_CONTROL.relative_to(ROOT)}:1:{private_path}"]
    finally:
        NEGATIVE_CONTROL.unlink(missing_ok=True)


def _forbidden_patterns() -> tuple[str, ...]:
    return (
        "/".join(("", "Users", "hosung")),
        "".join(("Penn", "sylvania")),
        "-".join(("OneDrive", "SharedLibraries")),
        "-".join(("Hosung", "Research")),
        " ".join(("AI", "Adoption", "Meta", "Analysis")),
    )


def _text_files(roots: Iterable[Path]) -> Iterable[Path]:
    for root in roots:
        if root.is_file():
            yield root
            continue
        for path in root.rglob("*"):
            if path.is_file() and not _is_generated(path):
                yield path


def _is_generated(path: Path) -> bool:
    parts = set(path.parts)
    return "__pycache__" in parts or ".pytest_cache" in parts


def _scan(paths: Sequence[Path], patterns: Sequence[str]) -> list[str]:
    findings: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for pattern in patterns:
                if pattern in line:
                    findings.append(f"{path.relative_to(ROOT)}:{line_number}:{pattern}")
    return findings
