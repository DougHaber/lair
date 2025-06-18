import lair.components.tools
from lair.logging import logger


class ToolSet:
    def __init__(self, *, tools=None):
        """
        Create a collection of tools

        Arguments:
           tools: A list of tool classes to include. When not provided, the default tools are included
        """
        self.requested_tools = None
        self.tools = {}  # function name -> {}
        self._init_tools(tools)

    def _init_tools(self, tools):
        self.requested_tools = lair.components.tools.DEFAULT_TOOLS if tools is None else tools

        # Instantiate each tool collection and register the tools in our ToolSet() instance
        for tool in self.requested_tools:
            tool().add_to_tool_set(self)

    def update_tools(self, tools=None):
        """
        Recreate all tools in the tool set

        Arguments:
           tools: A list of tool classes to include. When not provided, the default tools are included
        """
        self._init_tools(tools)

    def add_tool(self, *, name, flags, definition=None, definition_handler=None, handler, class_name):
        """
        Register a new tool

        Arguments:
          flags: A list of config keys, each of which must be true for the tool to be enabled
          definition: The structured definition of the function and its parameter in OpenAI API format
          definition_handler: A function that returns a definition, allowing for dynamic definitions.
              When provided, definition_handler takes precedence over definition
        """
        if name in self.tools:
            raise ValueError(f"ToolSet.add_tool(): A tool named '{name}' is already registered")
        elif not (definition or definition_handler):
            raise ValueError("ToolSet.add_tool(): Either a definition or a definition_handler must be provided")

        self.tools[name] = {
            "class_name": class_name,
            "definition": definition,
            "definition_handler": definition_handler,
            "flags": flags,
            "handler": handler,
            "name": name,
        }

    def get_tools(self):
        if not lair.config.get("tools.enabled"):
            return []

        enabled_tools = []
        for tool in self.tools.values():
            if not self.all_flags_enabled(tool["flags"]):
                continue

            enabled_tools.append(tool)

        return enabled_tools

    def all_flags_enabled(self, flags):
        for flag in flags:
            if not lair.config.get(flag):
                return False

        return True

    def get_all_tools(self):
        """
        Return all tools, adding in an extra 'enabled' field
        """
        all_tools = []
        for tool in self.tools.values():
            tool["enabled"] = lair.config.get("tools.enabled") and self.all_flags_enabled(tool["flags"]) is True
            all_tools.append(tool)

        return all_tools or None

    def _get_definition(self, tool):
        return tool["definition_handler"]() if tool["definition_handler"] else tool["definition"]

    def get_definitions(self):
        tools = self.get_tools()
        return [self._get_definition(tool) for tool in tools]

    def call_tool(self, name, arguments, tool_call_id):
        logger.debug(f"Tool call: {name}({arguments})  [{tool_call_id}]")
        if name not in self.tools:
            return {"error": f"Unknown tool: {name}"}

        try:
            return self.tools[name]["handler"](**arguments)
        except Exception as error:
            return {"error": f"Call failed: {error}"}
