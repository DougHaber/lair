from lair.config import Configuration


def create_config(tmp_path, yaml_text):
    home = tmp_path
    (home / ".lair").mkdir()
    (home / ".lair" / "config.yaml").write_text(yaml_text)
    return str(home)


def test_inherit_with_list(tmp_path, monkeypatch):
    home = create_config(
        tmp_path,
        """
foo:
  a: 1
bar:
  _inherit: [foo]
  b: 2
""",
    )
    monkeypatch.setenv("HOME", home)
    config = Configuration()
    assert config.modes["bar"]["a"] == 1
    assert config.modes["bar"]["b"] == 2


def test_inherit_with_string(tmp_path, monkeypatch):
    home = create_config(
        tmp_path,
        """
foo:
  a: 1
bar:
  _inherit: "['foo']"
  b: 2
""",
    )
    monkeypatch.setenv("HOME", home)
    config = Configuration()
    assert config.modes["bar"]["a"] == 1
    assert config.modes["bar"]["b"] == 2
