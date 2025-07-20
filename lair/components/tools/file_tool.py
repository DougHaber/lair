"""File system tools for use with :class:`~lair.components.tools.tool_set.ToolSet`."""

from __future__ import annotations

import datetime
import glob
import grp
import os
import pwd
import stat
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .tool_set import ToolSet

import lair
from lair.logging import logger


class FileTool:
    """Tools for manipulating files in the configured workspace."""

    name = "file"

    def __init__(self) -> None:
        """Initialize the tool."""
        pass

    def add_to_tool_set(self, tool_set: ToolSet) -> None:
        """Register file manipulation tools with a :class:`ToolSet`.

        Args:
            tool_set: The tool set to update with file operations.

        """
        tool_set.add_tool(
            class_name=self.__class__.__name__,
            name="list_directory",
            flags=["tools.allow_dangerous_tools", "tools.file.enabled"],
            definition_handler=lambda: self._generate_list_directory_definition(),
            handler=lambda *args, **kwargs: self.list_directory(*args, **kwargs),
        )
        tool_set.add_tool(
            class_name=self.__class__.__name__,
            name="read_file",
            flags=["tools.allow_dangerous_tools", "tools.file.enabled"],
            definition_handler=lambda: self._generate_read_file_definition(),
            handler=lambda *args, **kwargs: self.read_file(*args, **kwargs),
        )
        tool_set.add_tool(
            class_name=self.__class__.__name__,
            name="write_file",
            flags=["tools.allow_dangerous_tools", "tools.file.enabled", "tools.file.enable_writes"],
            definition_handler=lambda: self._generate_write_file_definition(),
            handler=lambda *args, **kwargs: self.write_file(*args, **kwargs),
        )
        tool_set.add_tool(
            class_name=self.__class__.__name__,
            name="delete_file",
            flags=["tools.allow_dangerous_tools", "tools.file.enabled", "tools.file.enable_deletes"],
            definition_handler=lambda: self._generate_delete_file_definition(),
            handler=lambda *args, **kwargs: self.delete_file(*args, **kwargs),
        )
        tool_set.add_tool(
            class_name=self.__class__.__name__,
            name="make_directory",
            flags=["tools.allow_dangerous_tools", "tools.file.enabled", "tools.file.enable_writes"],
            definition_handler=lambda: self._generate_make_directory_definition(),
            handler=lambda *args, **kwargs: self.make_directory(*args, **kwargs),
        )
        tool_set.add_tool(
            class_name=self.__class__.__name__,
            name="remove_directory",
            flags=["tools.allow_dangerous_tools", "tools.file.enabled", "tools.file.enable_deletes"],
            definition_handler=lambda: self._generate_remove_directory_definition(),
            handler=lambda *args, **kwargs: self.remove_directory(*args, **kwargs),
        )

    def _resolve_path(self, path: str) -> str:
        """Resolve a path relative to the workspace.

        Args:
            path: The input path, absolute or relative to the workspace.

        Returns:
            The absolute path within the workspace.

        Raises:
            ValueError: If the resolved path lies outside the workspace.

        """
        workspace = os.path.abspath(str(lair.config.get("tools.file.path")))
        if not os.path.isabs(path):
            path = os.path.join(workspace, path)
        absolute_path = os.path.abspath(path)
        if not absolute_path.startswith(workspace):
            raise ValueError(f"Access denied: {absolute_path} is outside the workspace.")
        return absolute_path

    def _generate_list_directory_definition(self) -> dict[str, Any]:
        """Return the definition for the ``list_directory`` tool."""
        workspace = lair.config.get("tools.file.path")
        return {
            "type": "function",
            "function": {
                "name": "list_directory",
                "description": (
                    f"List the contents of a directory within the workspace. "
                    f"Only files within the following path are accessible: {workspace}."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string", "description": "Directory path relative to the workspace."}
                    },
                    "required": ["directory"],
                },
            },
        }

    def list_directory(self, directory: str) -> dict[str, Any]:
        """List the contents of a directory within the workspace.

        Args:
            directory: The directory path relative to the workspace.

        Returns:
            Mapping with a ``contents`` key on success or an ``error`` key on failure.

        """
        try:
            dir_path = self._resolve_path(directory)
            if not os.path.isdir(dir_path):
                return {"error": f"Path '{dir_path}' is not a directory."}
            contents = []
            for item in os.listdir(dir_path):
                full_path = os.path.join(dir_path, item)
                st = os.stat(full_path)
                permissions = oct(stat.S_IMODE(st.st_mode))[2:]
                owner = pwd.getpwuid(st.st_uid).pw_name
                group = grp.getgrgid(st.st_gid).gr_name
                size = st.st_size
                last_modified = datetime.datetime.fromtimestamp(st.st_mtime).isoformat()
                contents.append(
                    {
                        "name": item,
                        "permissions": permissions,
                        "owner": owner,
                        "group": group,
                        "size": size,
                        "last_modified": last_modified,
                    }
                )
            return {"contents": contents}
        except Exception as error:
            logger.warning(f"list_directory(): Error encountered: {error}")
            return {"error": str(error)}

    def _generate_read_file_definition(self) -> dict[str, Any]:
        """Return the definition for the ``read_file`` tool."""
        workspace = lair.config.get("tools.file.path")
        return {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": (
                    f"Read the contents of one or more files within the workspace using a file path or glob pattern. "
                    f"Only files within the following path are accessible: {workspace}."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": (
                                "File path or glob pattern to read. (Supports all glob styles, "
                                "including recursive `**`)"
                            ),
                        }
                    },
                    "required": ["path"],
                },
            },
        }

    def read_file(self, path: str) -> dict[str, Any]:
        """Read files matched by ``path`` and return their contents.

        Args:
            path: File path or glob pattern relative to the workspace.

        Returns:
            Mapping with a ``file_content`` key on success or an ``error`` key on failure.

        """
        try:
            workspace = os.path.abspath(str(lair.config.get("tools.file.path")))

            pattern = os.path.join(workspace, path) if not os.path.isabs(path) else path

            file_paths = glob.glob(pattern, recursive=True)
            if not file_paths:
                return {"error": f"No files match the pattern: {path}"}

            file_contents = {}
            for file_path in file_paths:
                file_path = os.path.abspath(file_path)
                if not file_path.startswith(workspace):
                    return {"error": f"Access denied: {file_path} is outside the workspace."}
                elif not os.path.isfile(file_path):
                    continue  # Skip non-files (e.g., directories)

                with open(file_path) as f:
                    content = f.read()
                    relative_path = os.path.relpath(file_path, workspace)
                    file_contents[relative_path] = content

            return {"file_content": file_contents}
        except Exception as error:
            logger.warning(f"read_file(): Error encountered: {error}")
            return {"error": str(error)}

    def _generate_write_file_definition(self) -> dict[str, Any]:
        """Return the definition for the ``write_file`` tool."""
        workspace = lair.config.get("tools.file.path")
        return {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": (
                    f"Write provided content to a file within the workspace. "
                    f"Only files within the following path are accessible: {workspace}."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path relative to the workspace."},
                        "content": {"type": "string", "description": "Content to write into the file."},
                    },
                    "required": ["path", "content"],
                },
            },
        }

    def write_file(self, path: str, content: str) -> dict[str, Any]:
        """Write ``content`` to ``path`` within the workspace.

        Args:
            path: Destination file path relative to the workspace.
            content: Text to write to the file.

        Returns:
            Mapping with a ``message`` key on success or an ``error`` key on failure.

        """
        try:
            file_path = self._resolve_path(path)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w") as f:
                f.write(content)
            return {"message": f"File written to '{file_path}'."}
        except Exception as error:
            logger.warning(f"write_file(): Error encountered: {error}")
            return {"error": str(error)}

    def _generate_delete_file_definition(self) -> dict[str, Any]:
        """Return the definition for the ``delete_file`` tool."""
        workspace = lair.config.get("tools.file.path")
        return {
            "type": "function",
            "function": {
                "name": "delete_file",
                "description": (
                    f"Delete a file within the workspace. "
                    f"Only files within the following path are accessible: {workspace}."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string", "description": "File path relative to the workspace."}},
                    "required": ["path"],
                },
            },
        }

    def delete_file(self, path: str) -> dict[str, Any]:
        """Delete a file from the workspace.

        Args:
            path: File path relative to the workspace.

        Returns:
            Mapping with a ``message`` key on success or an ``error`` key on failure.

        """
        try:
            file_path = self._resolve_path(path)
            if not os.path.isfile(file_path):
                return {"error": f"Path '{file_path}' is not a file."}
            os.remove(file_path)
            return {"message": f"File '{file_path}' deleted."}
        except Exception as error:
            logger.warning(f"delete_file(): Error encountered: {error}")
            return {"error": str(error)}

    def _generate_make_directory_definition(self) -> dict[str, Any]:
        """Return the definition for the ``make_directory`` tool."""
        workspace = lair.config.get("tools.file.path")
        return {
            "type": "function",
            "function": {
                "name": "make_directory",
                "description": (
                    f"Create a directory within the workspace. "
                    f"Only files within the following path are accessible: {workspace}."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path relative to the workspace."}
                    },
                    "required": ["path"],
                },
            },
        }

    def make_directory(self, path: str) -> dict[str, Any]:
        """Create a directory inside the workspace.

        Args:
            path: Directory path relative to the workspace.

        Returns:
            Mapping with a ``message`` key on success or an ``error`` key on failure.

        """
        try:
            dir_path = self._resolve_path(path)
            os.makedirs(dir_path, exist_ok=True)
            return {"message": f"Directory '{dir_path}' created or already exists."}
        except Exception as error:
            logger.warning(f"make_directory(): Error encountered: {error}")
            return {"error": str(error)}

    def _generate_remove_directory_definition(self) -> dict[str, Any]:
        """Return the definition for the ``remove_directory`` tool."""
        workspace = lair.config.get("tools.file.path")
        return {
            "type": "function",
            "function": {
                "name": "remove_directory",
                "description": (
                    f"Remove an empty directory within the workspace. "
                    f"Only files within the following path are accessible: {workspace}."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Directory path relative to the workspace."}
                    },
                    "required": ["path"],
                },
            },
        }

    def remove_directory(self, path: str) -> dict[str, Any]:
        """Remove an empty directory from the workspace.

        Args:
            path: Directory path relative to the workspace.

        Returns:
            Mapping with a ``message`` key on success or an ``error`` key on failure.

        """
        try:
            dir_path = self._resolve_path(path)
            if not os.path.isdir(dir_path):
                return {"error": f"Path '{dir_path}' is not a directory."}
            os.rmdir(dir_path)
            return {"message": f"Directory '{dir_path}' removed."}
        except Exception as error:
            logger.warning(f"remove_directory(): Error encountered: {error}")
            return {"error": str(error)}
