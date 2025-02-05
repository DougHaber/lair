import lair.components.tools
from lair.logging import logger


class ToolSet():
    def __init__(self, *, tools=None):
        '''
        Create a collection of tools

        Arguments:
           tools: A list of tool classes to include. When not provided, the default tools are included
        '''
        self.requested_tools = lair.components.tools.DEFAULT_TOOLS if tools is None else tools
        self.tools = {}  # name -> {}
        self._init_tools()

    def _init_tools(self):
        # Instantiate each tool collection, allowing it to register each individual tool
        for tool in self.requested_tools:
            tool(self)

    def add_tool(self, *, name, flag, definition=None, definition_handler=None, handler, class_name):
        """
        Register a new tool

        Arguments:
          definition: The structured definition of the function and its parameter in OpenAI API format
          definition_handler: A function that returns a definition, allowing for dynamic definitions.
              When provided, definition_handler takes precedence over definition
        """
        if name in self.tools:
            raise ValueError(f"ToolSet.add_tool(): A tool named '{name}' is already registered")
        elif not (definition or definition_handler):
            raise ValueError("ToolSet.add_tool(): Either a definition or a definition_handler must be provided")

        self.tools[name] = {
            'class_name': class_name,
            'definition': definition,
            'definition_handler': definition_handler,
            'flag': flag,
            'handler': handler,
            'name': name,
        }

    def get_tools(self):
        enabled_tools = []
        for tool in self.tools.values():
            if lair.config.get('tools.enabled') and lair.config.get(tool['flag'] == True):
                continue

            enabled_tools.append(tool)

        return enabled_tools or None

    def get_all_tools(self):
        '''
        Return all tools, adding in an extra 'enabled' field
        '''
        all_tools = []
        for tool in self.tools.values():
            tool['enabled'] = lair.config.get('tools.enabled') and lair.config.get(tool['flag']) == True
            all_tools.append(tool)

        return all_tools or None

    def _get_definition(self, tool):
        return tool['definition_handler']() if tool['definition_handler'] else tool['definition']

    def get_definitions(self):
        tools = self.get_tools()
        return [self._get_definition(tool) for tool in tools]

    def call_tool(self, name, arguments, tool_call_id):
        logger.debug(f"Tool call: {name}({arguments})  [{tool_call_id}]")
        if name not in self.tools:
            raise ValueError(f"ToolSet().call_tool(): Call to undefined tool: {name}")

        return self.tools[name]['handler'](**arguments)
