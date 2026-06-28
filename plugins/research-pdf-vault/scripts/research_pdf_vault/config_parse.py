from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

TomlScalar: TypeAlias = str | int | float | bool
TomlValue: TypeAlias = TomlScalar | list["TomlValue"] | dict[str, "TomlValue"]
RawConfig: TypeAlias = Mapping[str, TomlValue]


@dataclass(frozen=True, slots=True)
class TomlConfigError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


def read_toml(path: Path) -> RawConfig:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as error:
        raise TomlConfigError(f"invalid TOML in {path}: {error}") from error


def optional_section(raw_config: RawConfig, key: str) -> RawConfig | None:
    raw_value = raw_config.get(key)
    if raw_value is None:
        return None
    if isinstance(raw_value, dict):
        return raw_value
    raise TomlConfigError(f"{key} must be a TOML table")


def optional_path(raw_config: RawConfig, key: str, base_dir: Path) -> Path | None:
    value = optional_str(raw_config, key)
    if value is None:
        return None
    return expand_path(Path(value), base_dir)


def optional_path_tuple(
    raw_config: RawConfig,
    key: str,
    base_dir: Path,
) -> tuple[Path, ...] | None:
    raw_value = raw_config.get(key)
    if raw_value is None:
        return None
    if isinstance(raw_value, list):
        return tuple(
            expand_path(Path(_string_item(item, key)), base_dir)
            for item in raw_value
        )
    raise TomlConfigError(f"{key} must be a list of paths")


def optional_str_tuple(raw_config: RawConfig, key: str) -> tuple[str, ...] | None:
    raw_value = raw_config.get(key)
    if raw_value is None:
        return None
    if isinstance(raw_value, list):
        return tuple(_string_item(item, key) for item in raw_value)
    raise TomlConfigError(f"{key} must be a list of strings")


def optional_str(raw_config: RawConfig, key: str) -> str | None:
    raw_value = raw_config.get(key)
    if raw_value is None:
        return None
    if isinstance(raw_value, str):
        if raw_value:
            return raw_value
        raise TomlConfigError(f"{key} must not be empty")
    raise TomlConfigError(f"{key} must be a string")


def optional_bool(raw_config: RawConfig, key: str) -> bool | None:
    raw_value = raw_config.get(key)
    if raw_value is None:
        return None
    if isinstance(raw_value, bool):
        return raw_value
    raise TomlConfigError(f"{key} must be a boolean")


def optional_int(raw_config: RawConfig, key: str) -> int | None:
    raw_value = raw_config.get(key)
    if raw_value is None:
        return None
    if isinstance(raw_value, bool):
        raise TomlConfigError(f"{key} must be an integer")
    if isinstance(raw_value, int):
        return raw_value
    raise TomlConfigError(f"{key} must be an integer")


def optional_float(raw_config: RawConfig, key: str) -> float | None:
    raw_value = raw_config.get(key)
    if raw_value is None:
        return None
    if isinstance(raw_value, bool):
        raise TomlConfigError(f"{key} must be a number")
    if isinstance(raw_value, int):
        return float(raw_value)
    if isinstance(raw_value, float):
        return raw_value
    raise TomlConfigError(f"{key} must be a number")


def expand_path(path: Path, base_dir: Path) -> Path:
    expanded = path.expanduser()
    if expanded.is_absolute():
        return expanded.resolve()
    return (base_dir / expanded).resolve()


def _string_item(value: TomlValue, field_name: str) -> str:
    if isinstance(value, str):
        if value:
            return value
        raise TomlConfigError(f"{field_name} entries must not be empty")
    raise TomlConfigError(f"{field_name} entries must be strings")
