"""Entry point for the ``lair`` command line interface."""

import argparse
import sys
import traceback
from typing import Any

import lair.logging
import lair.module_loader
import lair.reporting
import lair.util
from lair.logging import logger


def init_subcommands(parent_parser: argparse.ArgumentParser) -> dict[str, Any]:
    """
    Initialize all CLI subcommands.

    Args:
        parent_parser: The top level argument parser.

    Returns:
        Mapping of command names and aliases to instantiated command objects.

    """
    sub_parsers = parent_parser.add_subparsers(dest="subcommand")

    module_loader = lair.module_loader.ModuleLoader()
    module_loader.load_modules_from_path(lair.util.get_lib_path("modules/"))

    commands = {}
    for name, module in module_loader.modules.items():
        try:
            aliases = module.get("aliases", [])
            parser = sub_parsers.add_parser(name, help=module["description"], aliases=aliases)

            commands[name] = module["class"](parser)
            for alias in aliases:
                commands[alias] = commands[name]
        except Exception as error:
            raise Exception(f"Failed to load module '{name}': {error}") from error

    return commands


def parse_arguments() -> tuple[argparse.Namespace, Any]:
    """
    Parse command line arguments.

    Returns:
        A tuple containing the parsed arguments and the subcommand object to run.

    """

    class HelpFormatter(argparse.HelpFormatter):
        def _format_action(self, action: argparse.Action) -> str:
            """Format help output for subcommands."""
            if type(action) is argparse._SubParsersAction._ChoicesPseudoAction:
                return f"  {self._format_action_invocation(action):40.40} - {self._expand_help(action)}\n"
            return super()._format_action(action)

    parser = argparse.ArgumentParser(formatter_class=HelpFormatter)
    parser.add_argument("--debug", "-d", action="store_true", default=False, help="Enable debugging output")
    parser.add_argument(
        "--disable-color", "-c", action="store_true", default=False, help="Do not use color escape sequences"
    )
    parser.add_argument(
        "--force-color", "-C", action="store_true", default=False, help="Use color escape sequences, even in pipes"
    )
    parser.add_argument("-M", "--mode", type=str, help="Name of the predefined mode to use")
    parser.add_argument("-m", "--model", type=str, help="Name of the model to use")
    parser.add_argument("-s", "--set", action="append", type=str, help="Set a configuration value (-s key=value)")
    parser.add_argument("--version", action="store_true", default=False, help="Display the current version and exit")

    subcommands = init_subcommands(parser)
    arguments = parser.parse_args()

    if arguments.version:
        sys.stdout.write(f"Lair v{lair.version()}\n")
        sys.exit(0)
    elif not arguments.subcommand:
        parser.print_help()
        sys.exit(1)

    return arguments, subcommands[arguments.subcommand]


def set_config_from_arguments(overrides: list[str] | None) -> None:
    """
    Apply ``--set`` command line overrides to the active configuration.

    Args:
        overrides: A list of ``key=value`` strings to apply, or ``None``.

    """
    if not overrides:
        return

    for setting in overrides:
        if "=" not in setting:
            logger.error("Invalid usage of --set. Must use key=value style")
            sys.exit(1)
        else:
            key, value = setting.split("=", maxsplit=1)
            lair.config.set(key, value, no_event=True)

    lair.events.fire("config.update")


def _handle_error(error: Exception, arguments_defined: bool) -> None:
    logger.error(f"An error has occurred: ({error})\n")
    if not arguments_defined or lair.util.is_debug_enabled():
        traceback.print_exc()
        sys.exit(1)
    sys.exit("Enable debugging (--debug) for more details")


def start() -> None:
    """Initialize logging, parse arguments, and run the chosen subcommand."""
    try:
        lair.logging.init_logging()
        arguments, subcommand = parse_arguments()
        _configure_from_args(arguments)
        subcommand.run(arguments)
    except KeyboardInterrupt:
        sys.exit("Received interrupt.  Exiting")
    except Exception as error:
        _handle_error(error, "arguments" in locals())


def _configure_from_args(arguments: argparse.Namespace) -> None:
    """Apply runtime options from the CLI arguments."""
    if arguments.debug:
        logger.setLevel("DEBUG")
    if arguments.mode:
        lair.config.change_mode(arguments.mode)
    set_config_from_arguments(arguments.set)
    if arguments.model:
        lair.config.set("model.name", arguments.model)

    lair.reporting.Reporting(
        disable_color=arguments.disable_color,
        force_color=arguments.force_color,
    )
