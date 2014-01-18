"""
Tests for `biloba.util`.
"""

import unittest

import gevent

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


class WaitAnyTestCase(unittest.TestCase):
    """
    Tests for `util.waitany`
    """

    def never_return(self):
        """
        A function that will never return
        """
        from gevent import event

        ev = event.Event()

        ev.wait()

    def return_sync(self):
        """
        Return a result immediately.
        """
        return 5

    def return_async(self):
        """
        Force a context switch and when the greenlet is re-activated, return
        a result.
        """
        gevent.sleep(0.0)

        return 4

    def return_error(self):
        """
        Raise an exception synchronously
        """
        raise RuntimeError('foo bar')

    def return_error_async(self):
        """
        Force a context switch and when the greenlet is re-activated, raise an
        exception
        """
        gevent.sleep(0.0)

        raise RuntimeError('foo bar')

    def test_sync(self):
        """
        Ensure that synchronous greenlets are supported.
        """
        sync = gevent.spawn(self.return_sync)

        # the context switch forces the above greenlet to run, prepping its
        # value
        gevent.sleep(0.0)

        self.assertTrue(sync.ready())

        async = gevent.spawn(self.return_async)

        ret = util.waitany([async, sync])

        self.assertIs(ret, sync)

        self.assertEqual(ret.value, 5)

    def test_async(self):
        """
        Ensure that asynchronous greenlets are supported.
        """
        async = gevent.spawn(self.return_async)
        never = gevent.spawn(self.never_return)

        ret = util.waitany([async, never])

        self.assertIs(ret, async)

        self.assertEqual(ret.value, 4)

    def test_sync_error(self):
        sync = gevent.spawn(self.return_error)
        async = gevent.spawn(self.return_async)

        ret = util.waitany([async, sync])

        self.assertIs(ret, sync)

    def test_async_error(self):
        async = gevent.spawn(self.return_error_async)
        never = gevent.spawn(self.never_return)

        ret = util.waitany([never, async])

        self.assertIs(ret, async)
