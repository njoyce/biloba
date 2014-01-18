"""
Tests for `biloba.config`.
"""

import unittest

from biloba import config


class ParseAddressTestCase(unittest.TestCase):
    """
    Tests for `config.parse_address`
    """

    def test_address(self):
        """
        Ensure that is basically works
        """
        host, port = config.parse_address('foo:1234')

        self.assertEqual(host, 'foo')
        self.assertEqual(port, 1234)

    def test_no_port(self):
        host, port = config.parse_address('foo')

        self.assertEqual(host, 'foo')
        self.assertIsNone(port)

    def test_port_is_not_int(self):
        with self.assertRaises(ValueError):
            config.parse_address('foo:bar')


class GetKeyTestCase(unittest.TestCase):
    """
    Tests for `config.get_key`
    """

    config = {
        'foo': {
            'bar': [1, 2, 3],
        }
    }

    def test_missing_key(self):
        """
        Ensure that the default is returned when the key is missing from the
        config
        """
        self.assertIsNone(config.get_key(self.config, 'bar'))
        missing = object()

        ret = config.get_key(self.config, 'bar', missing)

        self.assertIs(ret, missing)

    def test_not_dotted(self):
        """
        A key on the first layer returns the correct value
        """
        self.assertEqual(
            config.get_key(self.config, 'foo'),
            self.config['foo']
        )

    def test_dotted(self):
        """
        dotted notation must be supported.
        """
        self.assertEqual(
            config.get_key(self.config, 'foo.bar'),
            self.config['foo']['bar']
        )


class ConfigTestCase(unittest.TestCase):
    """
    Tests for `config.Config`
    """

    my_config = {
        'http': {
            'address': '127.0.0.1',
            'port': 4000,
        },
        'logger': {
            'address': '${http.address}',
        }
    }

    def test_sanity(self):
        conf = config.Config(self.my_config)

        self.assertEqual(
            conf.get('logger.address'),
            '127.0.0.1'
        )

    def test_expand_list(self):
        my_config = {
            'foo': {
                'a': 'A',
                'b': 'B',
            },
            'bar': ['${foo.a}', 1, '${foo.b}']
        }

        conf = config.Config(my_config)

        self.assertEqual(
            conf['bar'],
            ['A', 1, 'B'],
        )

    def test_expand_dict(self):
        my_config = {
            'foo': {
                'a': 'A',
                'b': 'B',
            },
            'bar': {
                'c': '${foo.a}',
                'd': '${foo.b}'
            },
        }

        conf = config.Config(my_config)

        self.assertEqual(
            conf['bar'],
            dict(c='A', d='B'),
        )

    def test_setdefault(self):
        a = object()
        b = object()

        conf = config.Config()

        conf.setdefault('a', a)
        self.assertIs(conf['a'], a)
        conf.setdefault('a', b)
        self.assertIs(conf['a'], a)
