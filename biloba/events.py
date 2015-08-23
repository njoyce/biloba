# -*- coding: utf-8 -*-
"""
pyee
====

pyee supplies an ``EventEmitter`` object similar to the ``EventEmitter``
from Node.js.


Example
-------

::

    In [1]: from pyee import EventEmitter

    In [2]: ee = EventEmitter()

    In [3]: @ee.on('event')
       ...: def event_handler():
       ...:     print 'BANG BANG'
       ...:

    In [4]: ee.emit('event')
    BANG BANG

    In [5]:


Easy-peasy.
"""

import collections
import contextlib
import functools
import sys


__all__ = [
    'EventEmitter',
]


class EventEmitter(object):
    """
    The EventEmitter class.

    (Special) Events
    ----------------

    'new_listener': Fires whenever a new listener is created. Listeners for
        this event do not fire upon their own creation.

    'error': When emitted raises an Exception by default, behavior can be
        overriden by attaching callback to the event.

    For example::

        @ee.on('error')
        def on_rror(*exc_info):
            logging.error('something bad happened', exc_info=exc_info)

        ee.emit('error', Exception('something blew up'))
    """

    __slots__ = (
        '_events',
    )

    def __init__(self):
        """
        Initializes the emitter.
        """
        self._events = collections.defaultdict(list)

    def on(self, event, f=None):
        """Registers the function ``f`` to the event name ``event``.

        If ``f`` isn't provided, this method returns a function that
        takes ``f`` as a callback; in other words, you can use this method
        as a decorator, like so:

            @ee.on('data')
            def data_handler(data):
                print data

        """
        def _on(f):
            # Add the necessary function
            self.listeners(event).append(f)

            # Return original function so removal works
            return f

        if f is None:
            return _on
        else:
            return _on(f)

    def emit(self, event, *args, **kwargs):
        """
        Emit ``event``, passing ``*args`` to each attached function. Returns
        ``True`` if any functions are attached to ``event``; otherwise returns
        ``False``.

        Example:
            ee.emit('data', '00101001')

        Assuming ``data`` is an attached function, this will call
        ``data('00101001')'``.

        ``error`` is a special type of event. Either a single exception
        instance must be passed or the values from ``sys.exc_info()``. An
        example::

            ee.emit('error', *sys.exc_info())

            my_error = RuntimeError('foobar')

            ee.emit('error', my_error)

        All listeners to an error event will receive a sys.exc_info style
        tuple, even if an exception instance is supplied.

        If the ``error`` event is not handled, the exception is raised inline.
        """
        listeners = self.listeners(event)

        if event == 'error':
            # convert args in to a tuple as returned by sys.exc_info
            args = get_exc_info(*args)

            if not listeners:
                raise args[0], args[1], args[2]

        # Pass the args to each function in the events dict
        for func in listeners:
            func(*args, **kwargs)

        # whether the event was handled.
        return bool(listeners)

    def once(self, event, f=None):
        """The same as ``ee.on``, except that the listener is automatically
        removed after being called.
        """
        def _once(f):
            @functools.wraps(f)
            def g(*args, **kwargs):
                try:
                    self.remove_listener(event, g)
                finally:
                    f(*args, **kwargs)

            return g

        if f is None:
            return lambda f: self.on(event, _once(f))
        else:
            return self.on(event, _once(f))

    def remove_listener(self, event, f):
        """
        Removes the function ``f`` from ``event``.

        Requires that ``f`` is not closed over by ``ee.on``. (In other words,
        it is, unfortunately, not possible to use this with the decorator
        style is.)

        """
        self._events[event].remove(f)

    def remove_all_listeners(self, event=None):
        """
        Remove all listeners attached to ``event``.
        """
        if event is not None:
            self._events[event] = []
        else:
            self._events = None
            self._events = collections.defaultdict(list)

    def listeners(self, event):
        """
        Returns the list of all listeners registered to the ``event``.
        """
        return self._events[event]


@contextlib.contextmanager
def emit_exceptions(emitter, logger, propagate=True, always_log=False,
                    emit=True, skip_types=None):
    """
    A context manager that wraps a chunk of synchronous code and traps any
    exceptions. If an exception is caught and ``emit`` is ``True`` (the
    default), the ``emitter`` will emit an ``error`` event with the
    ``sys.exc_info()`` of the exception that was raised.

    A basic example looks like:

        import logging

        logging.basicConfig()

        ee = EventEmitter()

        @ee.on('error')
        def whoops(*exc_info):
            print('oh dear', exc_info)

        def blow_up():
            raise RuntimeError('foobar')

        with emit_exceptions(ee, logging):
            blow_up()

    The above example will print "oh dear <type 'exceptions.RuntimeError'> ..."
    and also raise the exception inline. This can be useful to ensure that the
    ``error`` event is sent but still have the normal try/except semantics
    still work.

    If an exception is raised when emitting the error, the exception is logged
    but the *original* exception is raised. Keep an eye on your logs ;)

    :param emitter: The event emitter that the `error` event will be
        dispatched from.
    :param logger: The logger that will handle any exceptions.
    :param propagate: Whether the context manager will re-raise the
        exception at `__exit__`.
    :param always_log: If an exception is raised, log the exception even if
        it is sent to the emitter. If `False`, exceptions will only be
        logged if there are no error handlers.
    :param skip_types: A list of exception types to avoid trapping. Exceptions
        of these types will be re-raised.
    """
    try:
        yield
    except (Exception, BaseException) as exc:
        if skip_types and isinstance(exc, skip_types):
            raise

        exc_info = sys.exc_info()
        handled = False

        # we have an exception, now to handle it. if the act of emitting the
        # error event causes an exception to be raised, log it out
        if emit:
            try:
                handled = emitter.emit('error', *exc_info)
            except (Exception, BaseException) as emit_exc:
                if skip_types and isinstance(emit_exc, skip_types):
                    emit_exc = None
                    handled = True

                if emit_exc is not None and emit_exc is not exc:
                    logger.exception(
                        'Exception raised while emitting error event',
                        exc_info=sys.exc_info()
                    )

        if not handled or always_log:
            logger.error('Exception was caught', exc_info=exc_info)

        if propagate:
            raise exc_info[0], exc_info[1], exc_info[2]


def get_exc_info(*args):
    """
    From a list of arguments, return a value that matches the format of
    ``sys.exc_info``.
    """
    if not args:
        raise TypeError('Expected at least one argument')

    if len(args) == 1:
        exc = args[0]

        try:
            if issubclass(exc, (Exception, BaseException)):
                exc = exc()
        except TypeError:
            pass

        if not isinstance(exc, (Exception, BaseException)):
            raise TypeError(
                'An exception instance must be supplied as the first argument '
                '(received:{!r})'.format(exc)
            )

        return exc.__class__, exc, None

    if len(args) != 3:
        raise TypeError(
            'Expected an exception instance or sys.exc_info() tuple'
        )

    exc_type, exc_value, exc_tb = args

    if not isinstance(exc_value, (Exception, BaseException)):
        raise TypeError(
            'exc_info tuple must be a valid exception instance '
            '(received:{!r}, {!r}, {!r})'.format(exc_type, exc_value, exc_tb)
        )

    return exc_type, exc_value, exc_tb
