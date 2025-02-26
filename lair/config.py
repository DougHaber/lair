import os
import sys

import lair.util
from lair.logging import logger  # noqa


class ConfigUnknownKeyException(Exception):
    pass


class ConfigInvalidType(Exception):
    pass


class Configuration():

    def __init__(self):
        self.modes = {}
        self.types = {}  # Preserve the valid type for each key (key -> type)
        self._init_default_mode()
        self.default_settings = self.modes['_default'].copy()  # Immutable copy of the defaults

        self.modes['_active'] = self.modes['_default'].copy()
        self.active = self.modes['_active']
        self.active_mode = '_default'

        if not os.path.isdir(os.path.expanduser('~/.lair/')):
            self._init_config_dir()

        self._load_config()

    def _load_config(self):
        config_filename = os.path.expanduser('~/.lair/config.yaml')
        if os.path.isfile(config_filename):
            config = lair.util.parse_yaml_file(config_filename)
            self._add_config(config)

    def _init_default_mode(self):
        self.modes['_default'] = lair.util.parse_yaml_text(
            lair.util.read_package_file('lair.files', 'settings.yaml'))
        default_mode = self.modes['_default']

        # Track the valid types, supporting overrides for null
        null_types = {
            '__null_float': float,
            '__null_int': int,
            '__null_str': str,
            '__null_bool': bool,
        }
        for key, value in default_mode.items():
            if not isinstance(value, str):
                self.types[key] = type(value)
            elif value in null_types:
                self.types[key] = null_types[value]
                default_mode[key] = None
            else:
                self.types[key] = type(value)

    def _init_config_dir(self):
        os.mkdir(os.path.expanduser('~/.lair/'))

        config_yaml = lair.util.read_package_file('lair.files', 'config.yaml')
        with open(os.path.expanduser('~/.lair/config.yaml'), 'w') as fd:
            fd.write(config_yaml)

    def _add_config(self, config):
        default_mode = None

        for mode, mode_config in config.items():
            if mode == 'default_mode':  # Default mode definition -- Not a real mode
                default_mode = config[mode]
            else:
                if mode not in self.modes:  # A newly defined mode starts with a copy of the defaults
                    self.modes[mode] = self.modes['_default'].copy()

                # If there is an `_inherit` section, copy each mode's settings in order
                for inherit_from_mode in mode_config.get('_inherit', []):
                    self.modes[mode].update(self.modes[inherit_from_mode])

                # Finally, give precedence to the mode's own settings
                self.modes[mode].update(mode_config)

        if default_mode is None:
            return
        elif default_mode not in self.modes:
            sys.exit("ERROR: Configuration file's default_mode is not found: %s" % default_mode)
        else:
            self.change_mode(default_mode)

    def change_mode(self, mode):
        if mode not in self.modes:
            raise Exception(f"Unknown mode: {mode}")

        # Reset `_active` to a fresh copy of the selected mode
        self.modes['_active'] = self.modes[mode].copy()
        self.active = self.modes['_active']
        self.active_mode = mode

        lair.events.fire('config.change_mode')
        lair.events.fire('config.update')

    def update(self, entries, *, force=False):
        """
        Updates only apply to the active runtime configuration.
        """
        if force:
            self.active.update(entries)
        else:
            for key, value in entries.items():
                self.set(key, value, no_event=True)

        lair.events.fire('config.update')

    def get(self, key, allow_not_found=False, default=None):
        """
        Retrieve a value from the active mode, failing if undefined unless `allow_not_found` is True.
        """
        if allow_not_found:
            return self.active.get(key, default)
        elif key in self.active:
            return self.active[key]
        else:
            raise ValueError(f"Configuration.get(): Attempt to retrieve unknown key: {key}")

    def set(self, key, value, *, force=False, no_event=False):
        """Only allow setting to the existing type."""
        if key == '_inherit':
            self.active[key] = value
            return
        elif key not in self.modes['_default']:
            raise ConfigUnknownKeyException("Unknown Key: %s" % key)

        no_cast = False
        current_type = self.types[key]
        if current_type is bool:
            if value in {True, 'true', 'True'}:
                value = True
            elif value in {False, 'false', 'False'}:
                value = False
            else:
                raise ConfigInvalidType(f"value '{value}' cannot be cast as '{current_type}' [key={key}]")
        elif value is None and current_type is str:
            value = ''
        elif (value == '' or value is None) and current_type in {bool, int, float}:
            value = None
            no_cast = True

        try:
            if not no_cast and value is not None:
                value = current_type(value)
            self.active[key] = value
            if not no_event:
                lair.events.fire('config.update')
        except ValueError:
            raise ConfigInvalidType(f"value '{value}' cannot be cast as '{current_type}'")

    def reload(self):
        """Ensure `_active` is properly reset instead of modifying mode definitions."""
        active_mode = self.active_mode

        self.modes = {}
        self.types = {}
        self._init_default_mode()

        if active_mode not in self.modes:
            active_mode = '_default'

        # Always start with a fresh copy for `_active`
        self.modes['_active'] = self.modes[active_mode].copy()
        self.active = self.modes['_active']
        self.active_mode = active_mode

        self._load_config()

        lair.events.fire('config.update')

    def get_modified_config(self):
        """
        Return a dictionary of the active configuration's settings that don't match the defaults.
        """
        return {k: v for k, v in self.active.items() if self.default_settings.get(k) != v}
