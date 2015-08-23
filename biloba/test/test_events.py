"""
Tests for ``biloba.events``
"""

import unittest
import mock

from biloba import events


class EventEmitterTestCase(unittest.TestCase):
    """
    Tests for ``events.EventEmitter``
    """

    def test_create(self):
        """
        Ensure that an EventEmitter can be instantiated.
        """
        emitter = events.EventEmitter()

        self.assertIsInstance(emitter, events.EventEmitter)

    def test_get_listeners(self):
        """
        ``EventEmitter.listeners`` must return a list for the event type.
        """
        emitter = events.EventEmitter()

        self.assertEqual(emitter.listeners('foobar'), [])

        @emitter.on('foobar')
        def foo_bar():
            pass

        self.assertEqual(emitter.listeners('foobar'), [foo_bar])

    def test_on_as_decorator(self):
        """
        Ensure that ``EventEmitter.on`` registers the listener when used as a
        decorator.
        """
        emitter = events.EventEmitter()

        self.assertEqual(emitter.listeners('foobar'), [])

        @emitter.on('foobar')
        def foo_bar():
            pass

        self.assertEqual(emitter.listeners('foobar'), [foo_bar])

    def test_on_functional(self):
        """
        Ensure that ``EventEmitter.on`` registers the listener when used in a
        purely functional manner
        """
        emitter = events.EventEmitter()

        self.assertEqual(emitter.listeners('foobar'), [])

        def foo_bar():
            pass

        emitter.on('foobar', foo_bar)

        self.assertEqual(emitter.listeners('foobar'), [foo_bar])

    def test_once_decorator(self):
        """
        Ensure that the listener is removed once the event is emitted (added
        as a decorator).
        """
        emitter = events.EventEmitter()

        self.assertEqual(emitter.listeners('foobar'), [])

        @emitter.once('foobar')
        def foo_bar():
            pass

        self.assertEqual(emitter.listeners('foobar'), [foo_bar])

        emitter.emit('foobar')

        self.assertEqual(emitter.listeners('foobar'), [])

    def test_once_functional(self):
        """
        Ensure that the listener is removed once the event is emitted (added in
        a purely functional manner).
        """
        emitter = events.EventEmitter()

        self.assertEqual(emitter.listeners('foobar'), [])

        def foo_bar():
            pass

        func = emitter.once('foobar', foo_bar)

        self.assertEqual(emitter.listeners('foobar'), [func])

        emitter.emit('foobar')

        self.assertEqual(emitter.listeners('foobar'), [])

    def test_once_error(self):
        """
        If the listener raises an exception, it MUST still be removed from the
        emitter.
        """
        emitter = events.EventEmitter()

        self.assertEqual(emitter.listeners('foobar'), [])

        def foo_bar():
            raise RuntimeError

        func = emitter.once('foobar', foo_bar)

        self.assertEqual(emitter.listeners('foobar'), [func])

        with self.assertRaises(RuntimeError):
            emitter.emit('foobar')

        self.assertEqual(emitter.listeners('foobar'), [])

    def test_remove_all_listeners(self):
        """
        ``EventEmitter.remove_all_listeners`` must do as expected.
        """
        emitter = events.EventEmitter()

        emitter.on('foo', lambda: None)
        emitter.on('bar', lambda: None)

        self.assertNotEqual(emitter.listeners('foo'), [])
        self.assertNotEqual(emitter.listeners('bar'), [])

        emitter.remove_all_listeners()

        self.assertEqual(emitter.listeners('foo'), [])
        self.assertEqual(emitter.listeners('bar'), [])

    def test_remove_all_listeners_event(self):
        """
        ``EventEmitter.remove_all_listeners`` with a supplied event must only
        remove those event listeneres.
        """
        emitter = events.EventEmitter()

        emitter.on('foo', lambda: None)
        emitter.on('bar', lambda: None)

        self.assertNotEqual(emitter.listeners('foo'), [])
        self.assertNotEqual(emitter.listeners('bar'), [])

        emitter.remove_all_listeners('foo')

        self.assertEqual(emitter.listeners('foo'), [])
        self.assertNotEqual(emitter.listeners('bar'), [])

    def test_emit_error_instance(self):
        """
        Emitting an ``error`` event must supply the correct args to the
        listener.
        """
        class TestException(Exception):
            pass

        emitter = events.EventEmitter()

        exc = TestException()

        self.executed = False

        @emitter.on('error')
        def on_error(exc_type, exc_value, exc_tb):
            self.assertIs(exc_type, TestException)
            self.assertIs(exc_value, exc)
            self.assertIsNone(exc_tb)

            self.executed = True

        emitter.emit('error', exc)

        self.assertTrue(self.executed)

    def test_emit_error_class(self):
        """
        Emitting an ``error`` event must supply the correct args to the
        listener.
        """
        class TestException(Exception):
            pass

        emitter = events.EventEmitter()

        self.executed = False

        @emitter.on('error')
        def on_error(exc_type, exc_value, exc_tb):
            self.assertIs(exc_type, TestException)
            self.assertIsInstance(exc_value, TestException)
            self.assertIsNone(exc_tb)

            self.executed = True

        emitter.emit('error', TestException)

        self.assertTrue(self.executed)

    def test_emit_error_tuple(self):
        """
        Emitting an ``error`` event must supply the correct args to the
        listener.
        """
        class TestException(Exception):
            pass

        emitter = events.EventEmitter()
        exc = TestException()

        self.executed = False

        @emitter.on('error')
        def on_error(exc_type, exc_value, exc_tb):
            self.assertIs(exc_type, TestException)
            self.assertIs(exc_value, exc)
            self.assertIsNone(exc_tb)

            self.executed = True

        emitter.emit('error', TestException, exc, None)

        self.assertTrue(self.executed)

    def test_emit_error_no_listeners(self):
        """
        Emitting an ``error`` event with no listeners MUST raise the exception.
        """
        class TestException(Exception):
            pass

        emitter = events.EventEmitter()
        exc = TestException()

        with self.assertRaises(TestException) as ctx:
            emitter.emit('error', exc)

        self.assertIs(ctx.exception, exc)


class GetExcInfoTestCase(unittest.TestCase):
    """
    Tests for ``events.get_exc_info``
    """

    def test_missing_args(self):
        """
        Supplying no args must raise a ``TypeError``.
        """
        with self.assertRaises(TypeError) as ctx:
            events.get_exc_info()

        self.assertEqual(
            unicode(ctx.exception),
            u'Expected at least one argument',
        )

    def test_not_an_exception(self):
        """
        Supplying one arg that is not an exception instance must raise a
        ``TypeError``.
        """
        with self.assertRaises(TypeError) as ctx:
            events.get_exc_info('foobar')

        self.assertEqual(
            unicode(ctx.exception),
            u"An exception instance must be supplied as the first argument "
            "(received:'foobar')",
        )

    def test_exception(self):
        """
        Supplying an exception instance must return a tuple in a
        ``sys.exc_info()`` style format.
        """
        class TestException(Exception):
            pass

        exc = TestException()
        ret = events.get_exc_info(exc)

        self.assertTupleEqual(ret, (TestException, exc, None))

    def test_exception_class(self):
        """
        Supplying an exception CLASS must return a tuple in a
        ``sys.exc_info()`` style format.
        """
        class TestException(Exception):
            pass

        ret = events.get_exc_info(TestException)

        self.assertEquals(len(ret), 3)
        exc_type, exc_value, exc_tb = ret

        self.assertIs(exc_type, TestException)
        self.assertIsInstance(exc_value, TestException)
        self.assertIsNone(exc_tb)

    def test_2_args(self):
        """
        Supplying 2 args must raise a ``TypeError``.
        """
        with self.assertRaises(TypeError):
            events.get_exc_info('foo', 'bar')

    def test_4_args(self):
        """
        Supplying 4 args must raise a ``TypeError``.
        """
        with self.assertRaises(TypeError):
            events.get_exc_info('foo', 'bar', 'baz', 'gak')

    def test_exc_tuple(self):
        """
        Supplying 3 args means that a return value from ``sys.exc_info()`` is
        being supplied.
        """
        with self.assertRaises(TypeError) as ctx:
            events.get_exc_info('foo', 'bar', 'baz')

        self.assertTrue(unicode(ctx.exception).startswith(
            u"exc_info tuple must be a valid exception instance"
        ))

    def test_return_sys_exc_info(self):
        """
        Supplying an exc_info tuple must return a tuple in a ``sys.exc_info()``
        style format.
        """
        exc_info = (RuntimeError, RuntimeError(), None)

        self.assertEqual(
            events.get_exc_info(*exc_info),
            exc_info
        )


class EmitExceptionsTestCase(unittest.TestCase):
    """
    Tests for ``events.emit_exceptions``
    """

    def emit_exceptions(self, emitter=None, logger=None, **kwargs):
        return events.emit_exceptions(
            emitter or mock.Mock(),
            logger or mock.Mock(),
            **kwargs
        )

    def test_no_exception(self):
        """
        If there is no exception raise, don't do anything.
        """
        with self.emit_exceptions():
            pass

    def test_skip_types(self):
        """
        If the exception type matches that supplied by omit then the exception
        must be raised.
        """
        class TestException(Exception):
            pass

        emitter = mock.Mock()

        with self.assertRaises(TestException):
            with self.emit_exceptions(emitter, skip_types=(TestException,)):
                raise TestException

    def test_propagate(self):
        """
        If propagate is ``True`` then the exception must be raised.
        """
        class TestException(Exception):
            pass

        emitter = mock.Mock()
        exc = TestException()

        with self.assertRaises(TestException):
            with self.emit_exceptions(emitter, propagate=True):
                raise exc

        mock_emit = emitter.emit
        mock_emit.assert_called_once()

        error, exc_type, exc_value, exc_tb = mock_emit.call_args[0]

        self.assertEqual(error, 'error')
        self.assertIs(exc_type, TestException)
        self.assertIs(exc_value, exc)
        self.assertIsNotNone(exc_tb)

    def test_no_propagate(self):
        """
        If propagate is ``False``, then the exception must NOT be raised.
        """
        class TestException(Exception):
            pass

        emitter = mock.Mock()
        exc = TestException()

        with self.emit_exceptions(emitter, propagate=False):
            raise exc

        mock_emit = emitter.emit
        mock_emit.assert_called_once()

        error, exc_type, exc_value, exc_tb = mock_emit.call_args[0]

        self.assertEqual(error, 'error')
        self.assertIs(exc_type, TestException)
        self.assertIs(exc_value, exc)
        self.assertIsNotNone(exc_tb)

    def test_no_emit(self):
        """
        If ``emit`` is False then the error event must NOT be emitted.
        """
        class TestException(Exception):
            pass

        emitter = mock.Mock()
        logger = mock.Mock()

        ctx = self.emit_exceptions(
            emitter,
            logger,
            emit=False,
            propagate=False
        )

        with ctx:
            raise TestException

        self.assertFalse(emitter.emit.called)
        self.assertTrue(logger.error.called)

    def test_always_log(self):
        """
        If ``always_log`` is True then any exception must be logged on the
        error level.
        """
        class TestException(Exception):
            pass

        logger = mock.Mock()

        ctx = self.emit_exceptions(
            logger=logger,
            always_log=True,
            propagate=False
        )

        with ctx:
            raise TestException

        self.assertTrue(logger.error.called)

    def test_exception_during_emit(self):
        """
        If an exception occurs while emitting the error event, it must be
        logged and the original exception raised (if propagate is True).
        """
        class TestException(Exception):
            pass

        emitter = mock.Mock()
        logger = mock.Mock()

        emitter.emit.side_effect = RuntimeError()

        ctx = self.emit_exceptions(
            emitter,
            logger,
            propagate=True
        )

        with self.assertRaises(TestException):
            with ctx:
                raise TestException

        self.assertTrue(logger.exception.called)

    def test_skip_exception_during_emit(self):
        """
        If an exception occurs while emitting the error event, AND it matches
        the supplied ``skip_types`` it must NOT be logged.
        """
        class TestException(Exception):
            pass

        emitter = mock.Mock()
        logger = mock.Mock()

        emitter.emit.side_effect = RuntimeError()

        ctx = self.emit_exceptions(
            emitter,
            logger,
            skip_types=(RuntimeError,)
        )

        with self.assertRaises(TestException):
            with ctx:
                raise TestException

        self.assertFalse(logger.exception.called)
