from lair import events


def test_subscribe_and_fire():
    called = []

    def handler(data):
        called.append(data)

    sub_id = events.subscribe('unit', handler)
    events.fire('unit', {'value': 1})
    events.unsubscribe(sub_id)

    assert called == [{'value': 1}]


def test_defer_events():
    called = []

    def handler(data):
        called.append(data)

    sub_id = events.subscribe('defer', handler)
    with events.defer_events():
        events.fire('defer', {'v': 1})
        events.fire('defer', {'v': 1})  # should be squashed
    events.unsubscribe(sub_id)

    assert called == [{'v': 1}]
