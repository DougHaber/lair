import os
import re
import time

import lair
from lair.logging import logger

import libtmux

# TODO: Review descriptions and parameters for each command

class TmuxTool:
    name = 'tmux'
    # TODO: Cleanups of old docker sessions / log files

    def __init__(self, tool_set):
        self.server = None
        self.session = None

        self.log_files = {}    # Mapping from pane_id to log file path
        self.log_offsets = {}  # Mapping from pane_id to current file read offset

        tool_set.add_tool(
            class_name=self.__class__.__name__,
            name='run',
            flags=['tools.tmux.enabled', 'tools.tmux.run.enabled'],
            definition_handler=lambda: self._generate_run_definition(),
            handler=lambda *args, **kwargs: self.run()
        )
        tool_set.add_tool(
            class_name=self.__class__.__name__,
            name='send_keys',
            flags=['tools.tmux.enabled', 'tools.tmux.send_keys.enabled', 'tools.allow_dangerous_tools'],
            definition_handler=lambda: self._generate_send_keys_definition(),
            handler=lambda *args, **kwargs: self.send_keys(**kwargs)
        )
        tool_set.add_tool(
            class_name=self.__class__.__name__,
            name='capture_output',
            flags=['tools.tmux.enabled', 'tools.tmux.capture_output.enabled'],
            definition_handler=lambda: self._generate_capture_output_definition(),
            handler=lambda *args, **kwargs: self.capture_output()
        )
        tool_set.add_tool(
            class_name=self.__class__.__name__,
            name='read_new_output',
            flags=['tools.tmux.enabled', 'tools.tmux.read_new_output.enabled'],
            definition_handler=lambda: self._generate_read_new_output_definition(),
            handler=lambda *args, **kwargs: self.read_new_output(**kwargs)
        )
        tool_set.add_tool(
            class_name=self.__class__.__name__,
            name='attach_window',
            flags=['tools.tmux.enabled', 'tools.tmux.attach_window.enabled'],
            definition_handler=lambda: self._generate_attach_window_definition(),
            handler=lambda *args, **kwargs: self.attach_window(**kwargs)
        )
        tool_set.add_tool(
            class_name=self.__class__.__name__,
            name='kill',
            flags=['tools.tmux.enabled', 'tools.tmux.kill.enabled'],
            definition_handler=lambda: self._generate_kill_definition(),
            handler=lambda *args, **kwargs: self.kill()
        )
        tool_set.add_tool(
            class_name=self.__class__.__name__,
            name='list_windows',
            flags=['tools.tmux.enabled', 'tools.tmux.list_windows.enabled'],
            definition_handler=lambda: self._generate_list_windows_definition(),
            handler=lambda *args, **kwargs: self.list_windows()
        )

    def _connect_to_tmux(self):
        self.server = libtmux.Server()
        self.session = None

        for session in self.server.sessions:
            if session.name == lair.config.get('tools.tmux.session_name'):
                self.session = session
                break

        if not self.session:
            self.session = self.server.new_session(session_name=lair.config.get('tools.tmux.session_name'),
                                                   attach=False)

    def _ensure_connection(self):
        try:
            if self.server is None:  # First time connecting in
                self._connect_to_tmux()
            self.server.list_sessions()
        except Exception as error:
            logger.error(f"Tmux server connection error: {e}. Attempting to reconnect.")
            try:
                self._connect_to_tmux()
            except Exception as connect_error:
                # TODO: On fail, clean up old connections?
                raise Exception(f"Tmux server unavailable: {connect_error}")

    def _get_output(self, return_mode, *, prune_line=None):
        '''
        Return the output dict based on the return_mode
        '''
        if return_mode == "new":
            return self.read_new_output(prune_line=prune_line)
        elif return_mode == "full":
            return self.capture_output()

    def _generate_run_definition(self):
        return {
            "type": "function",
            "function": {
                "name": "run",
                "description": (
                    f"Create a new tmux window. {lair.config.get('tools.tmux.run.description')}"
                    "Optionally wait a short delay and return output from the new window. "
                    "Set return_mode to 'new' (default) for new output or 'full' for a full screen capture."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "delay": {
                            "type": "number",
                            "description": "Delay (in seconds) before capturing output after window creation.",
                            "default": 2.0
                        },
                        "return_mode": {
                            "type": "string",
                            "description": "Output mode: 'new' (default) or 'full'.",
                            "default": "new"
                        }
                    }
                }
            }
        }

    def get_log_file_name_and_create_directories(self, window):
        template = lair.config.get('tools.tmux.capture_file_name').format(
            pid=os.getpid(),
            window_id=window.get('window_id'),
        )

        file_name = os.path.expanduser(template)

        # Create parent directories
        directory = os.path.dirname(file_name)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        return file_name

    def run(self, *, delay=2.0, return_mode="new"):
        try:
            self._ensure_connection()

            if len(self.session.windows) >= lair.config.get('tools.tmux.window_limit'):
                return {"error": "Window limit reached. Close an existing window before opening a new one."}
            elif return_mode not in {'new', 'full'}:
                return {"error": "run(): return_mode must be either 'new' or 'full'"}

            window = self.session.new_window(window_name="lair", attach=False)
            window.set_window_option("remain-on-exit", "on")
            pane = window.attached_pane or window.active_pane
            pane_id = pane.get("pane_id")

            log_file_name = self.get_log_file_name_and_create_directories(window)
            # Set up a log file and attach the pipe before sending the command.
            with open(log_file_name, 'w'):
                pass

            self.log_files[pane_id] = log_file_name
            self.log_offsets[pane_id] = 0
            pane.cmd('pipe-pane', '-o', f'cat >> {log_file_name}')

            logger.debug(f"TmuxTool(): run(): window_id={window.get('window_id')}, pane_id={pane.get("pane_id")}, "
                         f"logfile={log_file_name}")

            pane.send_keys(lair.config.get('tools.tmux.run.command'))
            time.sleep(delay)

            return {
                "window_id": window.get("window_id"),
                "message": "Window created",
                **self._get_output(return_mode=return_mode),
            }
        except Exception as error:
            import traceback; traceback.print_exc()
            return {"error": str(error)}

    def _generate_send_keys_definition(self):
        return {
            "type": "function",
            "function": {
                "name": "send_keys",
                "description": (
                    "Send keys to the active pane of the most recently created tmux window in session 'lair'. "
                    "Parameters: keys (string), enter (boolean, default true), literal (boolean, default true), "
                    "return_mode (string, default 'new'), and delay (number, default 0.2 seconds)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "keys": {"type": "string", "description": "The key sequence to send."},
                        "enter": {"type": "boolean", "description": "Whether to send Enter after keys.", "default": True},
                        "literal": {"type": "boolean", "description": "Send keys literally if true.", "default": True},
                        "return_mode": {"type": "string", "description": "Output mode: 'new' or 'full'.", "default": "new"},
                        "delay": {
                            "type": "number",
                            "description": "Delay (in seconds) before capturing output. Set longer for long-running commands.",
                            "default": 0.2
                        }
                    },
                    "required": ["keys"]
                }
            }
        }

    def send_keys(self, keys, enter=True, literal=True, return_mode="new", delay=0.2):
        try:
            self._ensure_connection()

            if not self.session.windows:
                return {"error": "No active tmux windows available."}
            elif return_mode not in {'new', 'full'}:
                return {"error": "send_keys(): return_mode must be either 'new' or 'full'"}

            window = self.session.windows[-1]
            pane = window.attached_pane or window.active_pane

            pane.send_keys(keys, enter=enter, literal=literal)
            time.sleep(delay)

            return self._get_output(return_mode=return_mode,
                                    prune_line=keys if enter else None)
        except Exception as e:
            return {"error": str(e)}

    def _generate_capture_output_definition(self):
        return {
            "type": "function",
            "function": {
                "name": "capture_output",
                "description": (
                    "Capture the entire output from the active pane of the most recently created tmux window in session 'lair'."
                ),
                "parameters": {"type": "object", "properties": {}}
            }
        }

    def capture_output(self):
        try:
            self._ensure_connection()
            if not self.session.windows:
                return {"error": "No active tmux windows available."}

            window = self.session.windows[-1]
            pane = window.attached_pane or window.active_pane

            return {"current_screen": '\n'.join(pane.capture_pane())}
        except Exception as error:
            return {"error": str(error)}

    def _generate_read_new_output_definition(self):
        return {
            "type": "function",
            "function": {
                "name": "read_new_output",
                "description": (
                    "Read new output from the active pane of the most recently created tmux window in session 'lair'. "
                    "Only new output since the last read is returned, up to a maximum number of bytes."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "max_size": {
                            "type": "integer",
                            "description": "Maximum number of bytes to return. Default is 1024.",
                            "default": 1024
                        }
                    }
                }
            }
        }

    def read_new_output(self, max_size=1024, prune_line=None):
        """Read all new output from the piped file.

        Arguments:
          max_size (int): The maximum size to return. Only the last 'max_size' bytes of new data are
              returned.
          prune_line (str): When provided and tools.tmux.read_new_output.remove_echoed_commands is
              enabled, this will remove the first first line if it matches, so that echoed
              characters are sent back
        """
        try:
            self._ensure_connection()
            if not self.session.windows:
                return {"error": "No active tmux windows available."}
            # TODO: Output limit

            window = self.session.windows[-1]  # TODO: This style really work if a window is manually selected?
            pane = window.attached_pane or window.active_pane
            pane_id = pane.get("pane_id")

            if pane_id not in self.log_files:  # TODO: Cleanup
                return {"error": "Connection to pane lost. No log file found."}
            log_file = self.log_files[pane_id]
            offset = self.log_offsets.get(pane_id, 0)

            with open(log_file, 'rb') as f:
                f.seek(offset)
                new_data = f.read()
                new_offset = f.tell()

            new_data = new_data.decode('utf-8', errors='replace')
            new_data = new_data.replace('\r\n', '\n')

            if offset == 0:
                # If this is the first read, remove the first two lines
                # The first line is the command sent by run() being typed
                # The second is it echoing back with the prompt
                new_data = '\n'.join(new_data.splitlines()[2:])
            elif prune_line and lair.config.get('tools.tmux.read_new_output.remove_echoed_commands'):
                # If the first line matches the last sent input, prune it
                new_data = re.sub(rf'^{re.escape(prune_line)}\n', '', new_data)

            if lair.config.get('tools.tmux.read_new_output.strip_escape_codes'):
                new_data = lair.util.strip_escape_codes(new_data)
            if new_data.startswith('\r'):  # Skip the initial \r, since it adds no value
                new_data = new_data[1:]

            self.log_offsets[pane_id] = new_offset

            if len(new_data) > max_size:
                new_data = new_data[-max_size:]

            return {"output": new_data}
        except Exception as error:
            return {"error": str(error)}

    def _generate_kill_definition(self):
        return {
            "type": "function",
            "function": {
                "name": "kill",
                "description": "Close the most recently created tmux window in session 'lair'.",
                "parameters": {"type": "object", "properties": {}}
            }
        }

    def kill(self):
        try:
            self._ensure_connection()
            if not self.session.windows:
                return {"error": "No active tmux windows to kill."}

            window = self.session.windows[-1]
            window_id = window.get("window_id")
            window.kill_window()

            return {"message": f"Window {window_id} closed."}
        except Exception as error:
            return {"error": str(error)}

    def _generate_list_windows_definition(self):
        return {
            "type": "function",
            "function": {
                "name": "list_windows",
                "description": "List all tmux windows in session 'lair' with their IDs and names.",
                "parameters": {"type": "object", "properties": {}}
            }
        }

    def list_windows(self):
        try:
            self._ensure_connection()

            return {"windows": [
                {"window_id": window.get("window_id"), "window_name": window.get("window_name")}
                for window in self.session.windows
            ]}
        except Exception as error:
            return {"error": str(error)}

    def _generate_attach_window_definition(self):
        return {
            "type": "function",
            "function": {
                "name": "attach_window",
                "description": (
                    "Attach to an existing tmux window in session 'lair'. Specify window_id or window_name; "
                    "if none is provided, the most recently created window is attached."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "window_id": {"type": "string", "description": "The ID of the window to attach."},
                        "window_name": {"type": "string", "description": "The name of the window to attach."}
                    }
                }
            }
        }

    def attach_window(self, window_id=None, window_name=None):
        try:
            self._ensure_connection()

            if not self.session.windows:
                return {"error": "No tmux windows available to attach."}

            target_window = None
            if window_id:
                for window in self.session.windows:
                    if window.get("window_id") == window_id:
                        target_window = window
                        break
            elif window_name:
                for window in self.session.windows:
                    if window.get("window_name") == window_name:
                        target_window = window
                        break
            else:
                target_window = self.session.windows[-1]

            if not target_window:
                return {"error": "Specified window not found."}

            target_window.select_window()
            return {"message": f"Attached to window {target_window.get('window_id')} ({target_window.get('window_name')})."}
        except Exception as error:
            return {"error": str(error)}
