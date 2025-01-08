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
        null_str_types = {
            '__null_float': float,
            '__null_int': int,
            '__null_str': str,
            '__null_bool': bool,
        }
        for key, value in default_mode.items():
            if not isinstance(value, str):
                self.types[key] = type(value)
            elif value in null_str_types:
                self.types[key] = null_str_types[value]
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
            if mode == 'default_mode':
                # Default mode settings -- Not a real mode
                default_mode = config[mode]
            else:
                if mode not in self.modes:
                    self.modes[mode] = self.modes['_default'].copy()

                self.update(mode_config, mode=mode)

        if default_mode is None:
            return
        elif default_mode not in self.modes:
            sys.exit("ERROR: Configuration file's default_mode is not found: %s" % default_mode)
        else:
            self.active = self.modes[default_mode]
            self.active_mode = default_mode

    def change_mode(self, mode):
        if mode not in self.modes:
            raise Exception(f"Unknown mode: {mode}")

        self.active = self.modes[mode]
        self.active_mode = mode

        lair.events.fire('config.change_mode')
        lair.events.fire('config.update')

    def update(self, entries, *, force=False, mode=None):
        mode = mode or self.active_mode

        if force is True:
            self.modes[mode].update(entries)
        else:
            for key, value in entries.items():
                self.set(key, value, mode=mode, no_event=True)

        lair.events.fire('config.update')

    def get(self, *args, **kwargs):
        mode = kwargs.get('mode', self.active_mode)
        if 'mode' in kwargs:  # Delete the mode override so it isn't passed to the real get()
            del kwargs['mode']

        return self.modes[mode].get(*args, **kwargs)

    def set(self, key, value, *, force=False, mode=None, no_event=False):
        """Only allow setting to the existing type."""
        mode = mode or self.active_mode
        if force is True:
            self.modes[mode][key] = value
            if not no_event:
                lair.events.fire('config.update')
            return

        if key not in self.modes['_default']:
            raise ConfigUnknownKeyException("Unknown Key: %s" % key)

        no_cast = False
        current_type = self.types[key]
        if current_type is bool:
            if value is True or value == 'true' or value == 'True':
                value = True
            elif value is False or value == 'false' or value == 'False':
                value = False
            else:
                raise ConfigInvalidType("value '%s' can not be cast as '%s' [key=%s]" % (value, current_type, key))
        elif value is None and current_type is str:
            value = ''
        elif (value == '' or value is None) and current_type in {bool, int, float}:
            value = None
            no_cast = True

        try:
            if not no_cast:
                value = current_type(value)
            self.modes[mode][key] = value
            if not no_event:
                lair.events.fire('config.update')
        except ValueError:
            raise ConfigInvalidType("value '%s' can not be cast as '%s'" % (value, current_type))

    def reload(self):
        active_mode = self.active_mode

        self.modes = {}
        self.types = {}
        self._init_default_mode()

        if active_mode not in self.modes:
            active_mode = '_default'

        self.modes['_active'] = self.modes[active_mode].copy()
        self.active = self.modes['_active']
        self.active_mode = active_mode

        self._load_config()

        lair.events.fire('config.update')
