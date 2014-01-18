from gevent import event


class cachedproperty(object):
    """
    A decorator that converts a method in to a property and caches the value
    returned by that method for fast retrieval.
    """

    def __init__(self, func):
        self.func = func

    def __get__(self, obj, *args, **kwargs):
        if obj is None:
            return self

        value = self.func(obj)

        setattr(obj, self.func.__name__, value)

        return value


def waitany(greenlets, timeout=None, result_class=event.AsyncResult):
    """
    Given a list of greenlets, wait for the first one to return a result.

    Note that only the greenlet is returned, not the value (or the exception).

    :param greenlets: A list of greenlets.
    :param timeout: The maximum amount of time to wait before raising
        `gevent.Timeout`. A timeout of `None` means to wait potentially
        forever.
    :param result_class: Advanced usage and tests.
    :return: The greenlet that first returned a result.
    """
    result = result_class()
    update = result.set

    try:
        for thread in greenlets:
            # start is idempotent :)
            thread.start()

            if not thread.ready():
                thread.rawlink(update)

                continue

            # this greenlet contains a value already
            return thread

        return result.get(timeout=timeout)
    finally:
        for thread in greenlets:
            thread.unlink(update)
