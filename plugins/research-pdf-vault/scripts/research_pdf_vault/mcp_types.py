from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias, TypeGuard

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class McpToolError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    input_schema: JsonObject

    def to_json(self) -> JsonObject:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


@dataclass(frozen=True, slots=True)
class IntArgSpec:
    key: str
    default: int
    minimum: int
    maximum: int


def is_json_object(value: JsonValue) -> TypeGuard[JsonObject]:
    return type(value) is dict


def string_arg(arguments: JsonObject, key: str) -> str:
    raw_value = arguments.get(key)
    if type(raw_value) is str and raw_value:
        return raw_value
    raise McpToolError(f"{key} must be a non-empty string")


def optional_string_arg(arguments: JsonObject, key: str) -> str | None:
    raw_value = arguments.get(key)
    if raw_value is None:
        return None
    if type(raw_value) is str and raw_value:
        return raw_value
    raise McpToolError(f"{key} must be a non-empty string")


def bounded_int_arg(arguments: JsonObject, spec: IntArgSpec) -> int:
    raw_value = arguments.get(spec.key)
    if raw_value is None:
        return spec.default
    if type(raw_value) is int and not isinstance(raw_value, bool):
        if spec.minimum <= raw_value <= spec.maximum:
            return raw_value
        raise McpToolError(
            f"{spec.key} must be between {spec.minimum} and {spec.maximum}",
        )
    raise McpToolError(f"{spec.key} must be an integer")


def bool_arg(arguments: JsonObject, key: str, default: bool) -> bool:
    raw_value = arguments.get(key)
    if raw_value is None:
        return default
    if type(raw_value) is bool:
        return raw_value
    raise McpToolError(f"{key} must be a boolean")
