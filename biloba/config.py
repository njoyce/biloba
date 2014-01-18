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
        value = get_key(self.config, key, default=default)

        return self.expand(value)

    def setdefault(self, key, value):
        original_value = self.get(key, missing)

        if original_value is missing:
            self.config[key] = value

    def __getitem__(self, key):
        return self.get(key)


def get_key(config, key, default=None):
    """
    Uses a dotted notation to traverse a dict.
    """
    val = config

    for part in key.split('.'):
        val = val.get(part, missing)

        if val is missing:
            return default

    return val or default


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
