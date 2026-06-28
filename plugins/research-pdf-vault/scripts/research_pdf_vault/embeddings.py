from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum, unique
from typing import Protocol, assert_never


@unique
class EmbeddingBackendKind(StrEnum):
    FIXTURE = "fixture"


@dataclass(frozen=True, slots=True)
class EmbeddingBackendError(Exception):
    backend_name: str

    def __str__(self) -> str:
        return f"unsupported embedding backend: {self.backend_name}"


class EmbeddingBackend(Protocol):
    name: str

    def embed(self, text: str) -> tuple[float, ...]:
        ...


@dataclass(frozen=True, slots=True)
class FixtureEmbeddingBackend:
    name: str = EmbeddingBackendKind.FIXTURE.value

    def embed(self, text: str) -> tuple[float, ...]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return tuple(round(digest[index] / 255, 6) for index in range(8))


def embedding_backend_for(name: str) -> EmbeddingBackend:
    try:
        kind = EmbeddingBackendKind(name)
    except ValueError as error:
        raise EmbeddingBackendError(backend_name=name) from error
    match kind:
        case EmbeddingBackendKind.FIXTURE:
            return FixtureEmbeddingBackend()
        case unreachable:
            assert_never(unreachable)
