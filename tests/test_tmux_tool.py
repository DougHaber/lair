import os
import lair
import pytest
from lair.components.tools.tmux_tool import TmuxTool


class DummyPane:
    def __init__(self, pane_id):
        self._pane_id = pane_id
        self.sent = []
        self.cmds = []
        self.captured = []

    def get(self, key):
        if key == 'pane_id':
            return self._pane_id

    def send_keys(self, keys, enter=True, literal=True):
        self.sent.append((keys, enter, literal))

    def cmd(self, *args):
        self.cmds.append(args)

    def capture_pane(self):
        return self.captured


class DummyWindow:
    def __init__(self, window_id, name='window'):
        self._id = f'@{window_id}' if not str(window_id).startswith('@') else str(window_id)
        self._name = name
        self.attached_pane = DummyPane(f'%{window_id}')
        self.killed = False
        self.selected = False

    @property
    def active_pane(self):
        return self.attached_pane

    def get(self, key):
        if key == 'window_id':
            return self._id
        if key == 'window_name':
            return self._name

    def kill_window(self):
        self.killed = True

    def select_window(self):
        self.selected = True


class DummySession:
    def __init__(self):
        self.windows = []

    def new_window(self, window_name, attach=False):
        win = DummyWindow(len(self.windows)+1, window_name)
        self.windows.append(win)
        return win

    def list_windows(self):
        return list(self.windows)


def setup_config(tmp_path):
    cfg = lair.config
    keys = [
        'tools.tmux.window_limit',
        'tools.tmux.capture_file_name',
        'tools.tmux.run.command',
        'tools.tmux.read_new_output.remove_echoed_commands',
        'tools.tmux.read_new_output.strip_escape_codes',
        'tools.tmux.read_new_output.max_size_default',
        'tools.tmux.read_new_output.max_size_limit',
    ]
    old = {k: cfg.get(k) for k in keys}
    cfg.set('tools.tmux.window_limit', 3, no_event=True)
    cfg.set('tools.tmux.capture_file_name', os.path.join(str(tmp_path), 'cap-{window_id}.log'), no_event=True)
    cfg.set('tools.tmux.run.command', 'echo hi', no_event=True)
    cfg.set('tools.tmux.read_new_output.remove_echoed_commands', True, no_event=True)
    cfg.set('tools.tmux.read_new_output.strip_escape_codes', False, no_event=True)
    cfg.set('tools.tmux.read_new_output.max_size_default', 1024, no_event=True)
    cfg.set('tools.tmux.read_new_output.max_size_limit', 8192, no_event=True)
    return old


def restore_config(values):
    for k, v in values.items():
        lair.config.set(k, v, no_event=True)


@pytest.fixture
def tool(tmp_path):
    old = setup_config(tmp_path)
    tool = TmuxTool()
    tool._ensure_connection = lambda: None
    tool.session = DummySession()
    yield tool
    restore_config(old)


def test_get_window_by_id_and_errors(tool):
    session = tool.session
    w1 = session.new_window('one')
    session.new_window('two')
    assert tool._get_window_by_id(w1.get('window_id')) is w1
    assert tool._get_window_by_id(w1.get('window_id').lstrip('@')) is w1
    assert tool._get_window_by_id(None) is None
    with pytest.raises(Exception):
        tool._get_window_by_id('@99')


def test_get_output_modes(tool, monkeypatch):
    called = {}

    def fake_read(**kwargs):
        called['mode'] = 'stream'
        return {'out': 'stream'}

    def fake_cap(**kwargs):
        called['mode'] = 'screen'
        return {'out': 'screen'}

    monkeypatch.setattr(tool, 'read_new_output', fake_read)
    monkeypatch.setattr(tool, 'capture_output', fake_cap)
    assert tool._get_output('stream') == {'out': 'stream'}
    assert called['mode'] == 'stream'
    assert tool._get_output('screen') == {'out': 'screen'}
    assert called['mode'] == 'screen'
    with pytest.raises(Exception):
        tool._get_output('bad')


def test_run_creates_window_and_logs(tool, tmp_path, monkeypatch):
    monkeypatch.setattr(TmuxTool, '_get_output', lambda self, **k: {'ok': True})
    monkeypatch.setattr(os, 'getpid', lambda: 12345)
    monkeypatch.setattr('time.sleep', lambda x: None)
    result = tool.run(delay=0, return_mode='stream')
    assert result['ok'] is True
    assert 'window_id' in result
    assert tool.active_window in tool.session.windows
    pane = tool.active_window.attached_pane
    log_file = tool.log_files[pane.get('pane_id')]
    assert os.path.isfile(log_file)
    assert ('pipe-pane', '-o', f'cat >> {log_file}') in pane.cmds

    # window limit error
    tool.session.windows = [object()] * lair.config.get('tools.tmux.window_limit')
    err = tool.run(return_mode='stream')
    assert 'limit reached' in err['error']

    # invalid return_mode
    tool.session.windows = []
    err2 = tool.run(return_mode='bad')
    assert 'return_mode' in err2['error']


def test_send_keys_valid_and_errors(tool, monkeypatch):
    # no windows
    err = tool.send_keys('ls')
    assert 'No active' in err['error']

    # create a window
    monkeypatch.setattr(TmuxTool, '_get_output', lambda self, **k: {'done': True})
    monkeypatch.setattr('time.sleep', lambda x: None)
    tool.run()
    pane = tool.active_window.attached_pane
    res = tool.send_keys('abc', enter=False, literal=False, return_mode='screen', delay=0)
    assert res['done'] is True
    assert pane.sent[-1] == ('abc', False, False)

    # invalid return_mode
    bad = tool.send_keys('abc', return_mode='bad')
    assert 'return_mode' in bad['error']


def test_capture_output_and_errors(tool):
    with pytest.raises(Exception):
        tool.capture_output()
    tool.session.new_window('one')
    tool.active_window = tool.session.windows[0]
    pane = tool.active_window.attached_pane
    pane.captured = ['a', 'b']
    out = tool.capture_output()
    assert out['current_screen'] == 'a\nb'


def test_read_new_output_flow(tool, tmp_path):
    win = tool.session.new_window('one')
    tool.active_window = win
    pane = win.attached_pane
    log = tmp_path / 'log.txt'
    tool.log_files[pane.get('pane_id')] = str(log)
    tool.log_offsets[pane.get('pane_id')] = 0
    data = b'cmd\nprompt\nhello\nworld\n'
    log.write_bytes(data)
    first = tool.read_new_output()
    assert first['output'] == 'hello\nworld'

    # append more with echoed command
    with open(log, 'ab') as f:
        f.write(b'ls\nresult\n')
    second = tool.read_new_output(prune_line='ls')
    assert second['output'] == 'result\n'

    # start with carriage return and large size
    with open(log, 'ab') as f:
        f.write(b'\ranother line\n')
    third = tool.read_new_output(max_size=8)
    assert third['output'].endswith('line\n')

    # connection lost
    del tool.log_files[pane.get('pane_id')]
    with pytest.raises(Exception):
        tool.read_new_output()


def test_kill_attach_and_list(tool):
    tool.session.new_window('one')
    tool.session.new_window('two')
    w1, w2 = tool.session.windows
    tool.active_window = w1

    msg = tool.kill(window_id=w1.get('window_id'))
    assert 'closed' in msg['message'] and w1.killed

    listed = tool.list_windows()['windows']
    assert any(d['window_name'] == 'two' for d in listed)

    attached = tool.attach_window(window_id=w2.get('window_id'))
    assert 'Attached' in attached['message'] and tool.active_window is w2 and w2.selected

    # errors when no windows
    tool.session.windows.clear()
    err = tool.kill(window_id='@1')
    assert 'No active tmux windows' in err['error']
    err2 = tool.attach_window(window_id='@1')
    assert 'No tmux windows' in err2['error']
