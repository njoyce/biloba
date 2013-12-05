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
