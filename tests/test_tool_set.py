import pytest
import lair
from lair.components.tools.tool_set import ToolSet


class DummyTool:
    def add_to_tool_set(self, tool_set):
        tool_set.add_tool(
            name='dummy',
            flags=['tools.file.enabled'],
            definition={'name': 'dummy'},
            handler=lambda value=None: {'value': value},
            class_name=self.__class__.__name__,
        )


class DynamicTool:
    def add_to_tool_set(self, tool_set):
        tool_set.add_tool(
            name='dynamic',
            flags=['tools.file.enabled', 'tools.allow_dangerous_tools'],
            definition_handler=lambda: {'name': 'dynamic'},
            handler=lambda: {'result': 'ok'},
            class_name=self.__class__.__name__,
        )


def test_update_tools_invokes_init(monkeypatch):
    called = []

    def fake_init(self, tools):
        called.append(tools)
    monkeypatch.setattr(ToolSet, '_init_tools', fake_init)

    ts = ToolSet(tools=[DummyTool])
    ts.update_tools([DynamicTool])

    assert called == [[DummyTool], [DynamicTool]]


def test_add_tool_validation_errors():
    ts = ToolSet(tools=[])
    ts.add_tool(
        name='a',
        flags=[],
        definition={'name': 'a'},
        handler=lambda: None,
        class_name='A',
    )
    with pytest.raises(ValueError):
        ts.add_tool(
            name='a',
            flags=[],
            definition={'name': 'a'},
            handler=lambda: None,
            class_name='A',
        )
    with pytest.raises(ValueError):
        ts.add_tool(name='b', flags=[], handler=lambda: None, class_name='B')


def test_get_tools_and_all_tools():
    ts = ToolSet(tools=[])
    DummyTool().add_to_tool_set(ts)
    DynamicTool().add_to_tool_set(ts)

    lair.config.set('tools.enabled', False, no_event=True)
    assert ts.get_tools() == []

    lair.config.set('tools.enabled', True, no_event=True)
    lair.config.set('tools.file.enabled', True, no_event=True)
    lair.config.set('tools.allow_dangerous_tools', False, no_event=True)

    tools = ts.get_tools()
    assert {t['name'] for t in tools} == {'dummy'}

    all_tools = ts.get_all_tools()
    assert {t['name']: t['enabled'] for t in all_tools} == {'dummy': True, 'dynamic': False}

    empty = ToolSet(tools=[])
    assert empty.get_all_tools() is None


def test_definitions_and_call_tool():
    ts = ToolSet(tools=[])
    DummyTool().add_to_tool_set(ts)
    DynamicTool().add_to_tool_set(ts)

    assert ts._get_definition(ts.tools['dummy']) == {'name': 'dummy'}
    assert ts._get_definition(ts.tools['dynamic']) == {'name': 'dynamic'}

    lair.config.set('tools.enabled', True, no_event=True)
    lair.config.set('tools.file.enabled', True, no_event=True)
    lair.config.set('tools.allow_dangerous_tools', True, no_event=True)

    defs = ts.get_definitions()
    assert {'name': 'dummy'} in defs and {'name': 'dynamic'} in defs

    ok = ts.call_tool('dummy', {'value': 5}, '123')
    assert ok == {'value': 5}

    err_unknown = ts.call_tool('missing', {}, '123')
    assert err_unknown['error'].startswith('Unknown tool')

    ts.add_tool(
        name='boom',
        flags=[],
        definition={'name': 'boom'},
        handler=lambda: 1/0,
        class_name='Boom',
    )
    err = ts.call_tool('boom', {}, '123')
    assert err['error'].startswith('Call failed')
