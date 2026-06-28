from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Final

from research_pdf_vault.schema import Sha256Hex

_WORD_RE: Final = re.compile(r"[a-z0-9]+")


def normalize_text_for_fingerprint(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(_WORD_RE.findall(normalized))


def text_fingerprint(text: str) -> Sha256Hex:
    normalized = normalize_text_for_fingerprint(text)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return Sha256Hex(digest)
