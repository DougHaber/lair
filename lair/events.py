"""Simple event subscription and dispatch utilities."""

import itertools
import weakref
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Optional

from lair.logging import logger

_event_handlers: dict[str, set[Callable[[object], object]]] = {}
_subscriptions: dict[int, tuple[str, Callable[[object], object]]] = {}
_next_subscription_id = itertools.count(1)  # Thread-safe ID generator
_instance_subscriptions: weakref.WeakKeyDictionary[object, set[int]] = weakref.WeakKeyDictionary()
# Tracks subscriptions by object

_deferring = False
_deferred_events: list[tuple[str, object]] = []
_squash_duplicates = True


def subscribe(event_name: str, handler: Callable[[object], object], instance: Optional[object] = None) -> int:
    """
    Subscribe a handler to an event.

    Args:
        event_name: Name of the event to subscribe to.
        handler: Callable executed when the event is fired.
        instance: Optional object to associate with the subscription. All
            subscriptions tied to this instance are cleaned up when the object
            is garbage collected.

    Returns:
        The subscription ID assigned to this handler.

    Raises:
        ValueError: If ``handler`` is not callable.

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


def _cleanup_instance_subscriptions(instance: object) -> None:
    """
    Remove all event subscriptions tied to ``instance``.

    Args:
        instance: Object whose event subscriptions should be removed.

    """
    if instance in _instance_subscriptions:
        for subscription_id in _instance_subscriptions.pop(instance, set()):
            unsubscribe(subscription_id)


def unsubscribe(subscription_id: int) -> bool:
    """
    Remove a subscription by ID.

    Args:
        subscription_id: Identifier returned by :func:`subscribe`.

    Returns:
        ``True`` if a subscription was removed, ``False`` otherwise.

    """
    if subscription_id in _subscriptions:
        event_name, handler = _subscriptions.pop(subscription_id)
        _event_handlers[event_name].discard(handler)
        if not _event_handlers[event_name]:
            del _event_handlers[event_name]  # Remove event if no handlers remain
        return True
    return False


def fire(event_name: str, data: object | None = None) -> bool:
    """
    Trigger an event and call all subscribed handlers.

    Args:
        event_name: Name of the event to fire.
        data: Optional payload to pass to each handler.

    Returns:
        ``True`` once all handlers have been invoked or queued.

    """
    if data is None:
        data = {}

    if _deferring:
        if not (_squash_duplicates and (event_name, data) in _deferred_events):
            _deferred_events.append((event_name, data))
        return True

    logger.debug(f"events: fire(): {event_name}, data: {data}")
    handlers = _event_handlers.get(event_name, set())
    for handler in list(handlers):  # Iterate over a copy to avoid modification issues
        if callable(handler):
            handler(data)
    return True


@contextmanager
def defer_events(squash_duplicates: bool = True) -> Iterator[None]:
    """
    Temporarily defer firing of events.

    Args:
        squash_duplicates: If ``True``, repeated events with the same payload are
            deduplicated while deferred.

    Yields:
        None

    """
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
