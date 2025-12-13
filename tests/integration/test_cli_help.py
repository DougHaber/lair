import pytest

from tests.helpers import run_cli


@pytest.mark.integration
def test_chat_help():
    result = run_cli("chat --help", expected_exit_code=0)
    assert "allow-create-session" in result.stdout.lower()
