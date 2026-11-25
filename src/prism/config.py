"""User configuration for prism."""

from __future__ import annotations

import dataclasses
import json
import tomllib
from pathlib import Path

import click
import platformdirs

APP_NAME = "prism"
CONFIG_FILENAME = "config.toml"
LEGACY_SHORTCUTS_FILENAME = "shortcuts.json"
CONFIG_KEYS = {"shortcuts"}


class ConfigError(Exception):
    """Raised when a configuration file cannot be used."""


@dataclasses.dataclass(frozen=True)
class Shortcut:
    """A single key binding loaded from configuration."""

    key: str
    action: str
    description: str
    show: bool = True
    key_display: str | None = None
    priority: bool = False


@dataclasses.dataclass(frozen=True)
class AppConfig:
    """Configuration values used by the application."""

    shortcuts: tuple[Shortcut, ...] | None = None


@dataclasses.dataclass(frozen=True)
class LoadedConfig:
    """A parsed configuration plus any non-fatal warnings."""

    config: AppConfig
    warnings: tuple[str, ...] = ()


def config_dir() -> Path:
    """Return the platform-specific configuration directory."""
    return Path(platformdirs.user_config_dir(APP_NAME))


def config_path() -> Path:
    """Return the path to prism's TOML configuration file."""
    return config_dir() / CONFIG_FILENAME


def legacy_shortcuts_path() -> Path:
    """Return the path to the pre-TOML shortcuts file."""
    return config_dir() / LEGACY_SHORTCUTS_FILENAME


def config_callback(
    ctx: click.Context, _param: click.Parameter, value: bool
) -> None:
    """Print the configuration path and exit without creating anything."""
    if not value or ctx.resilient_parsing:
        return
    click.echo(config_path())
    ctx.exit()


def _shortcut(
    item: object,
    *,
    source: Path,
    index: int,
    warnings: list[str],
) -> Shortcut:
    if not isinstance(item, dict):
        raise ConfigError(
            f"{source}: shortcuts[{index}] must be a table of key bindings"
        )

    required = ("key", "action", "description")
    for name in required:
        if not isinstance(item.get(name), str) or not item[name]:
            raise ConfigError(
                f"{source}: shortcuts[{index}] is missing string field {name!r}"
            )

    show = item.get("show", True)
    if not isinstance(show, bool):
        raise ConfigError(
            f"{source}: shortcuts[{index}].show must be a boolean"
        )

    priority = item.get("priority", False)
    if not isinstance(priority, bool):
        raise ConfigError(
            f"{source}: shortcuts[{index}].priority must be a boolean"
        )

    key_display = item.get("key_display")
    if key_display is not None and not isinstance(key_display, str):
        raise ConfigError(
            f"{source}: shortcuts[{index}].key_display must be a string"
        )

    allowed = {
        "key",
        "action",
        "description",
        "show",
        "key_display",
        "priority",
    }
    unknown = set(item) - allowed
    if unknown:
        names = ", ".join(sorted(unknown))
        warnings.append(
            f"{source}: ignoring unknown field(s) in shortcuts[{index}]: "
            f"{names}"
        )

    return Shortcut(
        key=item["key"],
        action=item["action"],
        description=item["description"],
        show=show,
        key_display=key_display,
        priority=priority,
    )


def _shortcuts(
    value: object, *, source: Path, warnings: list[str]
) -> tuple[Shortcut, ...]:
    if not isinstance(value, list):
        raise ConfigError(f"{source}: 'shortcuts' must be a list of tables")
    return tuple(
        _shortcut(
            item,
            source=source,
            index=index,
            warnings=warnings,
        )
        for index, item in enumerate(value)
    )


def _parse_toml(path: Path) -> LoadedConfig:
    try:
        with path.open("rb") as stream:
            data = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"{path}: {exc}") from exc

    warnings: list[str] = []
    unknown = set(data) - CONFIG_KEYS
    if unknown:
        names = ", ".join(sorted(unknown))
        warnings.append(
            f"{path}: ignoring unknown configuration key(s): {names}"
        )

    shortcuts = (
        _shortcuts(data["shortcuts"], source=path, warnings=warnings)
        if "shortcuts" in data
        else None
    )
    return LoadedConfig(AppConfig(shortcuts=shortcuts), tuple(warnings))


def _parse_legacy(path: Path) -> LoadedConfig:
    try:
        with path.open("r", encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"{path}: {exc}") from exc

    warnings: list[str] = []
    shortcuts = _shortcuts(data, source=path, warnings=warnings)
    warnings.append(
        f"{path}: legacy shortcuts file; move these entries to {config_path()}"
    )
    return LoadedConfig(AppConfig(shortcuts=shortcuts), tuple(warnings))


def load_config() -> LoadedConfig:
    """Load the user's configuration without touching the filesystem."""
    path = config_path()
    if path.is_file():
        return _parse_toml(path)

    legacy = legacy_shortcuts_path()
    if legacy.is_file():
        return _parse_legacy(legacy)

    return LoadedConfig(AppConfig())
