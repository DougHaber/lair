import pytest

import lair.events as events


def test_subscribe_and_fire():
    called = []

    def handler(data):
        called.append(data)

    sub_id = events.subscribe("unit", handler)
    events.fire("unit", {"value": 1})
    events.unsubscribe(sub_id)

    assert called == [{"value": 1}]


def test_defer_events():
    called = []

    def handler(data):
        called.append(data)

    sub_id = events.subscribe("defer", handler)
    with events.defer_events():
        events.fire("defer", {"v": 1})
        events.fire("defer", {"v": 1})  # should be squashed
    events.unsubscribe(sub_id)

    assert called == [{"v": 1}]


def test_subscribe_validation_and_cleanup(monkeypatch):
    with pytest.raises(ValueError):
        events.subscribe("bad", 123)

    called = []
    obj = type("T", (), {})()

    def handler(_):
        called.append(True)

    sub_id = events.subscribe("clean", handler, instance=obj)
    # simulate object cleanup
    events._cleanup_instance_subscriptions(obj)
    events.fire("clean")
    assert not called and sub_id not in events._subscriptions


def test_unsubscribe_missing():
    assert events.unsubscribe(99999) is False
