"""
Tests for `biloba.util`.
"""

import unittest

from biloba import util


class CachedPropertyTestCase(unittest.TestCase):
    """
    Tests for `util.cached_property`
    """

    class MyClass(object):
        @util.cachedproperty
        def foo(self):
            """
            Return a new object with a new `id` each time.
            """

            return object()

    def test_instance(self):
        """
        Simple test case for sanity
        """
        my_object = self.MyClass()

        foo = my_object.foo

        self.assertIs(foo, my_object.foo)

    def test_class(self):
        """
        Access `foo` as a class
        """
        self.assertIsInstance(
            self.MyClass.foo,
            util.cachedproperty
        )


