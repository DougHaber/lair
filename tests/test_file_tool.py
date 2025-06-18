import os
import lair
import pytest
from lair.components.tools.file_tool import FileTool


@pytest.fixture
def file_tool(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    lair.config.set('tools.file.path', str(workspace), no_event=True)
    return FileTool()


def test_resolve_path_within_and_outside(file_tool, tmp_path):
    base = tmp_path / "workspace"
    lair.config.set('tools.file.path', str(base), no_event=True)
    inside = file_tool._resolve_path('a.txt')
    assert inside == os.path.join(str(base), 'a.txt')
    with pytest.raises(ValueError):
        file_tool._resolve_path('../evil.txt')


def test_list_directory_basic(file_tool):
    workspace = lair.config.get('tools.file.path')
    f = os.path.join(workspace, 'file.txt')
    with open(f, 'w') as fd:
        fd.write('data')
    result = file_tool.list_directory('.')
    names = [e['name'] for e in result['contents']]
    assert 'file.txt' in names
    error = file_tool.list_directory('file.txt')
    assert "not a directory" in error['error']


def test_read_file_patterns_and_errors(file_tool, tmp_path):
    ws = tmp_path / "workspace"
    lair.config.set('tools.file.path', str(ws), no_event=True)
    (ws / 'a.txt').write_text('first')
    sub = ws / 'sub'
    sub.mkdir()
    (sub / 'b.txt').write_text('second')
    result = file_tool.read_file('**/*.txt')
    assert result['file_content'] == {'a.txt': 'first', os.path.join('sub', 'b.txt'): 'second'}
    error = file_tool.read_file('nomatch/*.txt')
    assert 'No files match' in error['error']
    outside = tmp_path / 'outside.txt'
    outside.write_text('bad')
    deny = file_tool.read_file(str(outside))
    assert 'outside the workspace' in deny['error']


def test_write_and_delete_file(file_tool):
    msg = file_tool.write_file('new/thing.txt', 'hello')
    path = file_tool._resolve_path('new/thing.txt')
    assert os.path.isfile(path)
    assert msg['message'].endswith(f"'{path}'.")
    with open(path) as fd:
        assert fd.read() == 'hello'
    bad = file_tool.write_file('../bad.txt', 'oops')
    assert 'outside the workspace' in bad['error']
    deleted = file_tool.delete_file('new/thing.txt')
    assert os.path.isfile(path) is False and 'deleted' in deleted['message']
    missing = file_tool.delete_file('none.txt')
    assert 'not a file' in missing['error']


def test_directory_creation_and_removal(file_tool):
    make = file_tool.make_directory('dir/sub')
    created = file_tool._resolve_path('dir/sub')
    assert os.path.isdir(created)
    assert 'created' in make['message']
    removed = file_tool.remove_directory('dir/sub')
    assert not os.path.isdir(created) and 'removed' in removed['message']
    error = file_tool.remove_directory('dir/sub')
    assert 'not a directory' in error['error']
