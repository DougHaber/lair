"""Lair configuration management utilities."""

import os
import sys
from collections.abc import Iterable, Mapping
from typing import cast

import lair.util
from lair.logging import logger  # noqa


class ConfigUnknownKeyError(Exception):
    """Raised when attempting to access an undefined configuration key."""

    pass


class ConfigInvalidTypeError(Exception):
    """Raised when a value cannot be cast to the expected configuration type."""

    pass


def _parse_inherit(value: str | Iterable[str]) -> list[str]:
    """
    Normalize the `_inherit` option to a list of mode names.

    Args:
        value: The raw `_inherit` value which may be a string or an iterable of
            strings.

    Returns:
        A list of mode names to inherit from.

    """
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned.startswith("[") and cleaned.endswith("]"):
            cleaned = cleaned[1:-1]
        if not cleaned:
            return []
        return [part.strip().strip("'").strip('"') for part in cleaned.split(",") if part.strip()]
    return list(value)


class Configuration:
    """Runtime and file-based configuration manager."""

    def __init__(self) -> None:
        """Initialize configuration modes and load user overrides."""
        self.modes: dict[str, dict[str, object]] = {}
        self.explicit_mode_settings: dict[str, dict[str, object]] = {}
        self.types: dict[str, type] = {}  # Preserve the valid type for each key (key -> type)
        self._init_default_mode()
        self.default_settings = self.modes["_default"].copy()  # Immutable copy of the defaults

        self.modes["_active"] = self.modes["_default"].copy()
        self.active = self.modes["_active"]
        self.active_mode = "_default"

        if not os.path.isdir(os.path.expanduser("~/.lair/")):
            self._init_config_dir()

        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from ``~/.lair/config.yaml`` if it exists."""
        config_filename = os.path.expanduser("~/.lair/config.yaml")
        if os.path.isfile(config_filename):
            config = lair.util.parse_yaml_file(config_filename)
            self._add_config(config)

    def _init_default_mode(self) -> None:
        """Populate the ``_default`` mode from package settings."""
        self.modes["_default"] = lair.util.parse_yaml_text(lair.util.read_package_file("lair.files", "settings.yaml"))
        default_mode = self.modes["_default"]

        # Track the valid types, supporting overrides for null
        null_types = {
            "__null_float": float,
            "__null_int": int,
            "__null_str": str,
            "__null_bool": bool,
        }
        for key, value in default_mode.items():
            if not isinstance(value, str):
                self.types[key] = type(value)
            elif value in null_types:
                self.types[key] = null_types[value]
                default_mode[key] = None
            else:
                self.types[key] = type(value)

    def _init_config_dir(self) -> None:
        """Create the ``~/.lair`` directory with a default configuration file."""
        os.mkdir(os.path.expanduser("~/.lair/"))

        config_yaml = lair.util.read_package_file("lair.files", "config.yaml")
        with open(os.path.expanduser("~/.lair/config.yaml"), "w") as fd:
            fd.write(config_yaml)

    def _add_config(self, config: Mapping[str, dict[str, object] | str]) -> None:
        """Merge a configuration dictionary into the existing modes."""
        default_mode: str | None = None

        for mode, mode_config in config.items():
            if mode == "default_mode":  # Default mode definition -- Not a real mode
                default_mode = str(config[mode])
            else:
                mode_dict = dict(cast(Mapping[str, object], mode_config))
                if mode not in self.modes:
                    # A newly defined mode starts with a copy of the defaults
                    self.modes[mode] = self.modes["_default"].copy()
                    # We also need a copy of only the keys that are explicitly set for inheritance
                    self.explicit_mode_settings[mode] = mode_dict.copy()

                # If there is an `_inherit` section, copy each mode's settings in order
                inherit = _parse_inherit(cast(str | Iterable[str], mode_dict.get("_inherit", [])))

                for inherit_from_mode in inherit:
                    self.modes[mode].update(self.explicit_mode_settings.get(inherit_from_mode, {}))

                # Finally, give precedence to the mode's own settings
                self.modes[mode].update(mode_dict)

        if default_mode is None:
            return
        elif default_mode not in self.modes:
            sys.exit(f"ERROR: Configuration file's default_mode is not found: {default_mode}")
        else:
            self.change_mode(default_mode)

    def change_mode(self, mode: str) -> None:
        """Switch to a different configuration mode."""
        if mode not in self.modes:
            raise Exception(f"Unknown mode: {mode}")

        # Reset `_active` to a fresh copy of the selected mode
        self.modes["_active"] = self.modes[mode].copy()
        self.active = self.modes["_active"]
        self.active_mode = mode

        lair.events.fire("config.change_mode")
        lair.events.fire("config.update")

    def update(self, entries: Mapping[str, object], *, force: bool = False) -> None:
        """
        Update only the active runtime configuration.

        Args:
            entries: Key-value pairs to update.
            force: Bypass type checking when ``True``.

        """
        if force:
            self.active.update(entries)
        else:
            for key, value in entries.items():
                self.set(key, value, no_event=True)

        lair.events.fire("config.update")

    def get(self, key: str, allow_not_found: bool = False, default: object | None = None) -> object | None:
        """
        Return a value from the active mode.

        Args:
            key: Configuration key to retrieve.
            allow_not_found: Return ``default`` instead of raising when the key is missing.
            default: Value to return when the key is not found and ``allow_not_found`` is ``True``.

        Returns:
            The configuration value.

        Raises:
            ValueError: If ``key`` is not defined and ``allow_not_found`` is ``False``.

        """
        if allow_not_found:
            return self.active.get(key, default)
        if key in self.active:
            return self.active[key]
        raise ValueError(f"Configuration.get(): Attempt to retrieve unknown key: {key}")

    def set(self, key: str, value: object, *, force: bool = False, no_event: bool = False) -> None:
        """
        Set a configuration value with type validation.

        Args:
            key: Configuration key to modify.
            value: New value for the key.
            force: Bypass type checking when ``True``.
            no_event: Do not fire update events when ``True``.

        Raises:
            ConfigUnknownKeyError: If ``key`` is not defined.
            ConfigInvalidTypeError: If ``value`` cannot be converted to the expected type.

        """
        if key == "_inherit":
            self.active[key] = value
            return

        if key not in self.modes["_default"]:
            raise ConfigUnknownKeyError(f"Unknown Key: {key}")

        try:
            value = self._cast_value(key, value)
            if value is not None and not isinstance(value, self.types[key]):
                value = self.types[key](value)
            self.active[key] = value
            if not no_event:
                lair.events.fire("config.update")

        except ValueError as error:
            raise ConfigInvalidTypeError(f"value '{value}' cannot be cast as '{self.types[key]}'") from error

    def _cast_value(self, key: str, value: object) -> object:
        """Cast ``value`` to the appropriate type for ``key`` if possible."""
        current_type = self.types[key]
        if current_type is bool:
            if value in {True, "true", "True"}:
                return True
            if value in {False, "false", "False"}:
                return False
            raise ConfigInvalidTypeError(f"value '{value}' cannot be cast as '{current_type}' [key={key}]")

        if value is None and current_type is str:
            return ""

        if (value == "" or value is None) and current_type in {bool, int, float}:
            return None

        return value

    def reload(self) -> None:
        """Reload configuration from disk without altering mode definitions."""
        active_mode = self.active_mode

        self.modes = {}
        self.types = {}
        self._init_default_mode()

        if active_mode not in self.modes:
            active_mode = "_default"

        # Always start with a fresh copy for `_active`
        self.modes["_active"] = self.modes[active_mode].copy()
        self.active = self.modes["_active"]
        self.active_mode = active_mode

        self._load_config()

        lair.events.fire("config.update")

    def get_modified_config(self) -> dict[str, object]:
        """Return the active configuration values that differ from the defaults."""
        return {k: v for k, v in self.active.items() if self.default_settings.get(k) != v}
