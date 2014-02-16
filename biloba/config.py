"""
Provides a simple interface around dict based config objects
"""

missing = object()


class Config(object):
    """
    A wrapper around a dict to provide a simpler interface for getting
    config values. Example::

        my_config = {
            'http': {
                'address': '127.0.0.1',
                'port': 4000,
            },
            'logger': {
                'address': '${http.address}',
            }
        }

        conf = Config(my_config)

        conf.get('logger.address') == '127.0.0.1'
    """

    def __init__(self, config=None):
        self.config = config or {}

    def expand(self, value):
        if isinstance(value, list):
            return [self.expand(sub_value) for sub_value in value]

        if isinstance(value, dict):
            ret = {}

            for key, sub_value in value.items():
                ret[key] = self.expand(sub_value)

            return ret

        if not isinstance(value, basestring):
            return value

        if not value.startswith('${'):
            return value

        key = value[2:-1]

        return self.get(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def setdefault(self, key, value):
        self.config.setdefault(key, value)

    def __getitem__(self, key):
        value = get_key(self.config, key)

        return self.expand(value)

    def __setitem__(self, key, value):
        self.config.__setitem__(key, value)

    def __contains__(self, key):
        return self.config.__contains__(key)

    def __eq__(self, other):
        return other == self.config


def get_key(config, key, default=missing):
    """
    Uses a dotted notation to traverse a dict.
    """
    val = config

    try:
        parts = key.split('.')
    except AttributeError:
        parts = [key]

    for part in parts:
        val = val.get(part, missing)

        if val is missing:
            if default is missing:
                raise KeyError(
                    '{!r} does not exist in {!r}'.format(key, config)
                )

            return default

    return val


def parse_address(address, port=None):
    """
    Return a (host, port) tuple based on the config value.
    """
    try:
        address, port = address.split(':', 1)
    except ValueError:
        pass

    if port:
        port = int(port)

    return address, port
