import os
import re
import time

import libtmux

import lair
from lair.logging import logger


class TmuxTool:
    name = "tmux"

    def __init__(self):
        self.server = None
        self.session = None

        self.log_files = {}  # Mapping from pane_id to log file path
        self.log_offsets = {}  # Mapping from pane_id to current file read offset

        self.active_window = None

    def add_to_tool_set(self, tool_set):
        tool_set.add_tool(
            class_name=self.__class__.__name__,
            name="run",
            flags=["tools.tmux.enabled", "tools.tmux.run.enabled"],
            definition_handler=lambda: self._generate_run_definition(),
            handler=lambda *args, **kwargs: self.run(),
        )
        tool_set.add_tool(
            class_name=self.__class__.__name__,
            name="send_keys",
            flags=["tools.tmux.enabled", "tools.tmux.send_keys.enabled", "tools.allow_dangerous_tools"],
            definition_handler=lambda: self._generate_send_keys_definition(),
            handler=lambda *args, **kwargs: self.send_keys(**kwargs),
        )
        tool_set.add_tool(
            class_name=self.__class__.__name__,
            name="capture_output",
            flags=["tools.tmux.enabled", "tools.tmux.capture_output.enabled"],
            definition_handler=lambda: self._generate_capture_output_definition(),
            handler=lambda *args, **kwargs: self.capture_output(),
        )
        tool_set.add_tool(
            class_name=self.__class__.__name__,
            name="read_new_output",
            flags=["tools.tmux.enabled", "tools.tmux.read_new_output.enabled"],
            definition_handler=lambda: self._generate_read_new_output_definition(),
            handler=lambda *args, **kwargs: self.read_new_output(**kwargs),
        )
        tool_set.add_tool(
            class_name=self.__class__.__name__,
            name="attach_window",
            flags=["tools.tmux.enabled", "tools.tmux.attach_window.enabled"],
            definition_handler=lambda: self._generate_attach_window_definition(),
            handler=lambda *args, **kwargs: self.attach_window(**kwargs),
        )
        tool_set.add_tool(
            class_name=self.__class__.__name__,
            name="kill",
            flags=["tools.tmux.enabled", "tools.tmux.kill.enabled"],
            definition_handler=lambda: self._generate_kill_definition(),
            handler=lambda *args, **kwargs: self.kill(),
        )
        tool_set.add_tool(
            class_name=self.__class__.__name__,
            name="list_windows",
            flags=["tools.tmux.enabled", "tools.tmux.list_windows.enabled"],
            definition_handler=lambda: self._generate_list_windows_definition(),
            handler=lambda *args, **kwargs: self.list_windows(),
        )

    def _connect_to_tmux(self):
        self.server = libtmux.Server()
        self.session = None
        self.active_window = None

        for session in self.server.sessions:
            if session.name == lair.config.get("tools.tmux.session_name"):
                self.session = session
                break

        if not self.session:
            self.session = self.server.new_session(
                session_name=lair.config.get("tools.tmux.session_name"), attach=False
            )
            self.log_files = {}
            self.log_offsets = {}

    def _get_window_by_id(self, window_id):
        if window_id is None:
            return None

        # We request window ids as ints, but tmux uses them as strings `@{id}`
        # This converts them back for the matching
        if isinstance(window_id, int) or not window_id.startswith("@"):
            window_id = f"@{window_id}"

        for window in self.session.list_windows():
            if window.get("window_id") == window_id:
                return window

        raise Exception(f"Requested window id not found: {window_id}")

    def _ensure_connection(self):
        try:
            if self.server is None:  # First time connecting in
                self._connect_to_tmux()
            self.server.list_sessions()
        except Exception as error:
            logger.error(f"Tmux server connection error: {error}. Attempting to reconnect.")
            try:
                self._connect_to_tmux()
            except Exception as connect_error:
                raise Exception(f"Tmux server unavailable: {connect_error}")

    def _get_output(self, return_mode, *, prune_line=None, window_id=None):
        """
        Return the output dict based on the return_mode
        """
        if return_mode == "stream":
            return self.read_new_output(prune_line=prune_line, window_id=window_id)
        elif return_mode == "screen":
            return self.capture_output(window_id=window_id)
        else:
            raise Exception("Invalid return_mode. Accepted values are stream or screen (screen capture)")

    def _generate_run_definition(self):
        return {
            "type": "function",
            "function": {
                "name": "run",
                "description": (f"Create a new tmux window. {lair.config.get('tools.tmux.run.description')} "),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "delay": {
                            "type": "number",
                            "description": "Delay (in seconds) before capturing output after window creation.",
                            "default": 2.0,
                        },
                        "return_mode": {
                            "type": "string",
                            "description": "Output mode: 'stream' (new terminal content) or 'screen' (string capture of the entire window).",
                            "enum": ["screen", "stream"],
                            "default": "stream",
                        },
                    },
                },
            },
        }

    def get_log_file_name_and_create_directories(self, window):
        template = lair.config.get("tools.tmux.capture_file_name").format(
            pid=os.getpid(),
            window_id=window.get("window_id"),
        )

        file_name = os.path.expanduser(template)

        # Create parent directories
        directory = os.path.dirname(file_name)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        return file_name

    def run(self, *, delay=2.0, return_mode="stream"):
        try:
            self._ensure_connection()

            if len(self.session.windows) >= lair.config.get("tools.tmux.window_limit"):
                return {"error": "Window limit reached. Close an existing window before opening a new one."}
            elif return_mode not in {"stream", "screen"}:
                return {"error": "run(): return_mode must be either 'stream' or 'screen'"}

            window = self.session.new_window(window_name="lair", attach=False)
            pane = window.attached_pane or window.active_pane
            pane_id = pane.get("pane_id")

            self.active_window = window

            log_file_name = self.get_log_file_name_and_create_directories(window)
            # Set up a log file and attach the pipe before sending the command
            with open(log_file_name, "w"):
                pass

            self.log_files[pane_id] = log_file_name
            self.log_offsets[pane_id] = 0
            pane.cmd("pipe-pane", "-o", f"cat >> {log_file_name}")

            logger.debug(
                f"TmuxTool(): run(): window_id={window.get('window_id')}, pane_id={pane.get("pane_id")}, "
                f"logfile={log_file_name}"
            )

            # NOTE: We are doing this instead of passing `window_shell` on creation so that the logging can be
            # setup first. Otherwise, we'd miss any initial output. The 'exec' is required so that the original
            # shell can not be accessed. The "exit" is a backup, in case the command fails to run.
            pane.send_keys(f"exec {lair.config.get('tools.tmux.run.command')}; exit")
            time.sleep(delay)

            return {
                "window_id": window.get("window_id"),
                "message": "Window created",
                **self._get_output(return_mode=return_mode),
            }
        except Exception as error:
            return {"error": str(error)}

    def _generate_send_keys_definition(self):
        return {
            "type": "function",
            "function": {
                "name": "send_keys",
                "description": "Send keys to the active or specified window. ",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "keys": {
                            "type": "string",
                            "description": "The key sequence to send. (libtmux style, literal=True by default)",
                        },
                        "delay": {
                            "type": "number",
                            "description": "Delay (in seconds) before capturing output. Set longer for long-running commands.",
                            "default": 0.2,
                        },
                        "enter": {
                            "type": "boolean",
                            "description": "Whether to send Enter after keys.",
                            "default": True,
                        },
                        "literal": {
                            "type": "boolean",
                            "description": "Send keys literally in libtmux style when true.",
                            "default": True,
                        },
                        "return_mode": {
                            "type": "string",
                            "description": "Output mode: 'stream' (new terminal content) or 'screen' (string capture of the entire window).",
                            "enum": ["screen", "stream"],
                            "default": "stream",
                        },
                        "window_id": {
                            "type": "number",
                            "description": "The id of the window to target. The default is the active window",
                        },
                    },
                    "required": ["keys"],
                },
            },
        }

    def send_keys(self, keys, enter=True, literal=True, return_mode="stream", delay=0.2, window_id=None):
        try:
            self._ensure_connection()

            if not self.session.windows:
                return {"error": "No active tmux windows available."}
            elif return_mode not in {"stream", "screen"}:
                return {"error": "send_keys(): return_mode must be either 'stream' or 'screen'"}

            window = self.active_window if window_id is None else self._get_window_by_id(window_id)
            pane = window.attached_pane or window.active_pane

            pane.send_keys(keys, enter=enter, literal=literal)
            time.sleep(delay)

            return self._get_output(return_mode=return_mode, prune_line=keys if enter else None, window_id=window_id)
        except Exception as e:
            return {"error": str(e)}

    def _generate_capture_output_definition(self):
        return {
            "type": "function",
            "function": {
                "name": "capture_output",
                "description": ("Return a screen capture of the active window as a string"),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "window_id": {
                            "type": "number",
                            "description": "The id of the window to target. The default is the active window",
                        }
                    },
                },
            },
        }

    def capture_output(self, *, window_id=None):
        self._ensure_connection()
        if not self.session.windows:
            raise Exception("No active tmux windows available.")

        window = self.active_window if window_id is None else self._get_window_by_id(window_id)
        pane = window.attached_pane or window.active_pane

        return {"current_screen": "\n".join(pane.capture_pane())}

    def _generate_read_new_output_definition(self):
        return {
            "type": "function",
            "function": {
                "name": "read_new_output",
                "description": "Read new output from the active window. Only new output since the last read is returned",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "max_size": {
                            "type": "integer",
                            "description": (
                                "Maximum number of bytes to return. If more bytes are available, only the "
                                "last `max_size` bytes are returned."
                            ),
                            "default": lair.config.get("tools.tmux.read_new_output.max_size_default"),
                        }
                    },
                },
            },
        }

    def read_new_output(self, max_size=1024, prune_line=None, window_id=None):
        """Read all new output from the piped file.

        Arguments:
          max_size (int): The maximum size to return. Only the last 'max_size' bytes of new data are
              returned.
          prune_line (str): When provided and tools.tmux.read_new_output.remove_echoed_commands is
              enabled, this will remove the first first line if it matches, so that echoed
              characters are sent back
        """
        self._ensure_connection()
        if not self.session.windows:
            raise Exception("No active tmux windows available.")

        max_size = min(
            max_size or lair.config.get("tools.tmux.read_new_output.max_size_default"),
            lair.config.get("tools.tmux.read_new_output.max_size_limit"),
        )

        pane_id, log_file, offset = self._get_pane_info(window_id)
        new_data, new_offset = self._read_pane_file(log_file, offset)
        new_data = self._clean_new_data(new_data, offset, prune_line)

        self.log_offsets[pane_id] = new_offset

        if len(new_data) > max_size:
            new_data = new_data[-max_size:]

        return {"output": new_data}

    def _get_pane_info(self, window_id):
        window = self.active_window if window_id is None else self._get_window_by_id(window_id)
        pane = window.attached_pane or window.active_pane
        pane_id = pane.get("pane_id")
        if pane_id not in self.log_files:
            raise Exception("Connection to pane lost.")
        log_file = self.log_files[pane_id]
        offset = self.log_offsets.get(pane_id, 0)
        return pane_id, log_file, offset

    def _read_pane_file(self, log_file, offset):
        with open(log_file, "rb") as f:
            f.seek(offset)
            new_data = f.read()
            new_offset = f.tell()
        return new_data, new_offset

    def _clean_new_data(self, new_data, offset, prune_line):
        text = new_data.decode("utf-8", errors="replace").replace("\r\n", "\n")

        if offset == 0:
            text = "\n".join(text.splitlines()[2:])
        elif prune_line and lair.config.get("tools.tmux.read_new_output.remove_echoed_commands"):
            text = re.sub(rf"^{re.escape(prune_line)}\n", "", text)

        if lair.config.get("tools.tmux.read_new_output.strip_escape_codes"):
            text = lair.util.strip_escape_codes(text)
        if text.startswith("\r"):
            text = text[1:]
        return text

    def _generate_kill_definition(self):
        return {
            "type": "function",
            "function": {
                "name": "kill",
                "description": "Close the specified tmux window.",
                "properties": {
                    "window_id": {"type": "string", "description": "The ID of the window to kill."},
                },
                "required": ["window_id"],
            },
        }

    def kill(self, *, window_id):
        try:
            self._ensure_connection()
            if not self.session.windows:
                return {"error": "No active tmux windows to kill."}

            window = self._get_window_by_id(window_id)
            window.kill_window()

            return {"message": f"Window {window_id} closed.  ({window.get('window_name')})"}
        except Exception as error:
            return {"error": str(error)}

    def _generate_list_windows_definition(self):
        return {
            "type": "function",
            "function": {
                "name": "list_windows",
                "description": "List all tmux windows with their IDs and names.",
                "parameters": {"type": "object", "properties": {}},
            },
        }

    def list_windows(self):
        try:
            self._ensure_connection()

            return {
                "windows": [
                    {"window_id": window.get("window_id"), "window_name": window.get("window_name")}
                    for window in self.session.windows
                ]
            }
        except Exception as error:
            return {"error": str(error)}

    def _generate_attach_window_definition(self):
        return {
            "type": "function",
            "function": {
                "name": "attach_window",
                "description": ("Attach to an existing tmux window by id, making it the default active window."),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "window_id": {"type": "string", "description": "The ID of the window to attach."},
                    },
                },
                "required": ["window_id"],
            },
        }

    def attach_window(self, *, window_id):
        try:
            self._ensure_connection()

            if not self.session.windows:
                return {"error": "No tmux windows available to attach."}

            window = self._get_window_by_id(window_id)
            self.active_window = window
            window.select_window()

            return {"message": f"Attached to window {window_id} ({window.get('window_name')})."}
        except Exception as error:
            return {"error": str(error)}
