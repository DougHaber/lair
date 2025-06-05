import importlib.machinery
import os
import re
import types

import jsonschema

from lair.logging import logger


class ModuleLoader():
    MODULE_INFO_SCHEMA = {
        'type': 'object',
        'properties': {
            'description': {'type': 'string'},
            'class': {},
            'tags': {'type': 'array', 'items': {'type': 'string'}},
            'aliases': {'type': 'array', 'items': {'type': 'string'}}
        },
        'required': ['class']
    }

    def __init__(self):
        self.modules = {}
        self.commands = {}

    def _get_module_files(self, path):
        module_files = []

        for root, dirs, files in os.walk(os.path.abspath(path)):
            for name in files:
                if name.endswith('.py') and name != '__init__.py' and not name.startswith('.'):
                    module_files.append('%s/%s' % (root, name))

        return module_files

    def _get_module_name(self, module, module_path):
        """Return the full name of the file by removing the module path and the extension.

        Example: `modules/util/tools/example.py` becomes just `util/tools/example`
        """
        absolute_module_file = os.path.abspath(module.__file__).replace('_', '-')
        absolute_module_path = os.path.abspath(module_path)

        return re.sub('^' + re.escape(absolute_module_path) + '/',
                      '',
                      re.sub(r'\.pyc?$', '', absolute_module_file))

    def _register_module(self, module, module_path):
        module_info = module._module_info()
        name = self._get_module_name(module, module_path)
        module_info.update({'name': name})  # Add the name into our stored module_info

        if name in self.modules:
            raise Exception("Unable to register repeat name: %s" % name)
        elif name in self.commands:
            raise Exception("Unable to register repeat command name: %s" % name)
        else:
            logger.debug("Registered module: %s" % name)
            self.modules[name] = module_info
            self.commands[name] = module_info['class']

            for alias in module_info.get('aliases', []):
                if alias in self.commands:
                    raise Exception("Unable to register repeat command / alias: %s" % name)
                self.commands[alias] = module_info['class']

    def _validate_module(self, module):
        if not hasattr(module, '_module_info'):
            raise Exception("_module_info not defined")
        elif not isinstance(module._module_info, types.FunctionType):
            raise Exception("_module_info not a function")
        else:
            try:
                jsonschema.validate(instance=module._module_info(),
                                    schema=ModuleLoader.MODULE_INFO_SCHEMA)
            except jsonschema.ValidationError as error:
                raise Exception("Invalid _module_info: %s" % error)

    def import_file(self, filename, module_path):
        logger.debug("Importing file: %s" % filename)

        try:
            spec = importlib.util.spec_from_file_location(filename, filename)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            self._validate_module(module)
            self._register_module(module, module_path)
        except Exception as error:
            logger.warning("Error loading module from file '%s': %s" % (filename, error))
            return

    def load_modules_from_path(self, module_path):
        logger.debug("Loading modules from path: %s" % module_path)
        files = self._get_module_files(module_path)

        for filename in sorted(files):
            self.import_file(filename, module_path)
