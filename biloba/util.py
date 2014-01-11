from gevent import event


class cachedproperty(object):
    """
    A decorator that converts a method in to a property and caches the value
    returned by that method for fast retrieval.
    """

    def __init__(self, func):
        self.func = func

    def __get__(self, obj, type=None):
        if obj is None:
            return self

        value = self.func(obj)

        setattr(obj, self.func.__name__, value)

        return value


def parse_address(address, port=None):
    try:
        address, port = address.split(':', 1)
    except ValueError:
        pass

    if port:
        port = int(port)

    return address, port


def waitany(events, timeout=None, result_class=event.AsyncResult):
    result = result_class()
    update = result.set

    try:
        for event in events:
            if not event.started:
                event.start()

            if event.ready():
                return event
            else:
                event.rawlink(update)

        return result.get(timeout=timeout)
    finally:
        for event in events:
            event.unlink(update)


def get_config_key(config, key, default=None):
    """
    Uses a dotted notation to traverse a dict.
    """
    val = config
    missing = object()

    for part in key.split('.'):
        val = val.get(part, missing)

        if val is missing:
            return default

    return val or default
