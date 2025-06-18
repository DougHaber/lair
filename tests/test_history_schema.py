import pytest
import jsonschema

from lair.components.history import schema


def test_validate_messages_success():
    messages = [{"role": "user", "content": "ok"}]
    assert schema.validate_messages(messages) is None


def test_validate_messages_invalid_root():
    with pytest.raises(jsonschema.exceptions.ValidationError) as exc:
        schema.validate_messages(5)
    assert "Validation failed at 'root'" in str(exc.value)


def test_validate_messages_invalid_role():
    msgs = [{"role": "bad", "content": "hi"}]
    with pytest.raises(jsonschema.exceptions.ValidationError) as exc:
        schema.validate_messages(msgs)
    assert "[0].role" in str(exc.value)
