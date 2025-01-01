event_handlers = {}  # event_name -> [handler, ...]


def subscribe(event_name, handler):
    global event_handlers

    handlers = event_handlers.setdefault(event_name, set())
    handlers.add(handler)


def unsubscribe(event_name, handler):
    global event_handlers

    if event_name not in event_handlers:
        return False
    else:
        handlers = event_handlers[event_name]
        handlers.remove(handler)


def fire(event_name, data={}):
    global event_handlers

    if event_name not in event_handlers:
        return False
    else:
        for handler in event_handlers[event_name]:
            handler(data)
