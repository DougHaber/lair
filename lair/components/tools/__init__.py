# from .core import *
from .tool_set import ToolSet
from .file_tool import FileTool
from .search_tool import SearchTool
from .python_tool import PythonTool


DEFAULT_TOOLS = [
    FileTool,
    SearchTool,
    PythonTool,
]

# Lookup for tool classes by their friendly names
TOOLS = {
    PythonTool.name: PythonTool,
    SearchTool.name: SearchTool,
}


def get_tool_class_by_name(name):
    return TOOLS.get(name)


def get_tool_classes_from_str(tool_names_str):
    '''
    Take a comma delimited list of tool names and return a list of classes
    '''
    classes = []
    for name in tool_names_str.split(','):
        name = name.strip()

        if name not in TOOLS:
            raise ValueError("Unknown tool name: %s" % tool_names_str)

        classes.append(TOOLS[name])
