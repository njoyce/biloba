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
