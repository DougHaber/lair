import pytest

from lair.components import tools


def test_get_tool_class_by_name_valid():
    cls = tools.get_tool_class_by_name("file")
    assert cls is tools.FileTool


def test_get_tool_class_by_name_invalid():
    assert tools.get_tool_class_by_name("missing") is None


def test_get_tool_classes_from_str_valid():
    # function currently returns None but should not raise
    result = tools.get_tool_classes_from_str("file,python")
    assert result is None


def test_get_tool_classes_from_str_unknown():
    with pytest.raises(ValueError):
        tools.get_tool_classes_from_str("file,unknown")
