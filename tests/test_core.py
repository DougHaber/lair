import lair.util.core as core


def test_safe_int():
    assert core.safe_int('5') == 5
    assert core.safe_int('abc') == 'abc'


def test_decode_jsonl():
    jsonl = '{"a":1}\n{"b":2}\n'
    assert core.decode_jsonl(jsonl) == [{"a": 1}, {"b": 2}]


def test_slice_from_str():
    data = [0, 1, 2, 3, 4, 5]
    assert core.slice_from_str(data, ':2') == [0, 1]
    assert core.slice_from_str(data, '1:4:2') == [1, 3]
    assert core.slice_from_str(data, '-2:') == [4, 5]


def test_expand_filename_list(tmp_path):
    f1 = tmp_path / 'one.txt'
    f2 = tmp_path / 'two.txt'
    f1.write_text('a')
    f2.write_text('b')
    pattern = str(tmp_path / '*.txt')
    result = core.expand_filename_list([pattern])
    assert str(f1) in result and str(f2) in result
