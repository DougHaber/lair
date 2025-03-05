from .file_tool import FileTool
from .python_tool import PythonTool
from .search_tool import SearchTool
from .tmux_tool import TmuxTool
from .tool_set import ToolSet


DEFAULT_TOOLS = [
    FileTool,
    PythonTool,
    SearchTool,
    TmuxTool,
 ]

# Lookup for tool classes by their friendly names
TOOLS = {
    FileTool.name: FileTool,
    PythonTool.name: PythonTool,
    SearchTool.name: SearchTool,
    TmuxTool.name: TmuxTool,
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
