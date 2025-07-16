import itertools
import weakref
from contextlib import contextmanager
from typing import Any, Callable

from lair.logging import logger

EventHandler = Callable[[dict[str, Any]], Any]

_event_handlers: dict[str, set[EventHandler]] = {}  # event_name -> {handler, ...}
_subscriptions: dict[int, tuple[str, EventHandler]] = {}  # subscription_id -> (event_name, handler)
_next_subscription_id: itertools.count = itertools.count(1)  # Thread-safe ID generator
_instance_subscriptions: weakref.WeakKeyDictionary[object, set[int]] = (
    weakref.WeakKeyDictionary()
)  # Tracks subscriptions by object

_deferring: bool = False
_deferred_events: list[tuple[str, dict[str, Any]]] = []
_squash_duplicates: bool = True


def subscribe(event_name, handler, instance=None):
    """
    Subscribe a handler to an event, optionally associating it with an instance.

    If an instance is provided, all its subscriptions will be auto-cleaned up when it is deleted.
    """
    if not callable(handler):
        raise ValueError(f"Handler for event '{event_name}' must be callable")

    _event_handlers.setdefault(event_name, set()).add(handler)

    subscription_id = next(_next_subscription_id)
    _subscriptions[subscription_id] = (event_name, handler)

    if instance:
        if instance not in _instance_subscriptions:
            _instance_subscriptions[instance] = set()
        _instance_subscriptions[instance].add(subscription_id)

        # Ensure automatic cleanup when instance is garbage collected
        weakref.finalize(instance, _cleanup_instance_subscriptions, instance)

    return subscription_id


def _cleanup_instance_subscriptions(instance):
    """Automatically removes all event subscriptions tied to an instance when it is deleted."""
    if instance in _instance_subscriptions:
        for subscription_id in _instance_subscriptions.pop(instance, set()):
            unsubscribe(subscription_id)


def unsubscribe(subscription_id):
    """Unsubscribes a handler using its subscription ID."""
    if subscription_id in _subscriptions:
        event_name, handler = _subscriptions.pop(subscription_id)
        _event_handlers[event_name].discard(handler)
        if not _event_handlers[event_name]:
            del _event_handlers[event_name]  # Remove event if no handlers remain
        return True
    return False


def fire(event_name, data={}):
    """Triggers an event, calling all subscribed handlers."""
    global _deferring
    if _deferring:
        if _squash_duplicates and any(event[0] == event_name and event[1] == data for event in _deferred_events):
            return  # Skip duplicate events
        _deferred_events.append((event_name, data))
        return

    logger.debug(f"events: fire(): {event_name}, data: {data}")
    if event_name in _event_handlers:
        for handler in list(_event_handlers[event_name]):  # Iterate over a copy to avoid modification issues
            if callable(handler):
                handler(data)
    return True


@contextmanager
def defer_events(squash_duplicates=True):
    """Context manager to defer and optionally deduplicate events until the context exits."""
    global _deferring, _squash_duplicates, _deferred_events
    _deferring = True
    _squash_duplicates = squash_duplicates
    _deferred_events = []
    try:
        yield
    finally:
        _deferring = False
        logger.debug("events: Starting to fire deferred events")
        for event_name, data in _deferred_events:
            fire(event_name, data)
        _deferred_events.clear()
        logger.debug("events: Finished firing deferred events")
