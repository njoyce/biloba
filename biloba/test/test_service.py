"""
Tests for `biloba.service`.
"""

import unittest
import mock

import gevent

from biloba import service


class SimpleService(service.Service):
    """
    Simple test service
    """
    def __init__(self):
        super(SimpleService, self).__init__()

    def do_start(self):
        """
        Start a simple service.
        """
        self.spawn(self.sleep)

    def sleep(self):
        """
        Sleep forever.
        """
        while True:
            gevent.sleep(1)


def make_service(logger=None):
    my_service = service.Service()

    if logger:
        my_service.logger = logger

    return my_service


class ServiceTestCase(unittest.TestCase):
    """
    Tests for `service.Service`
    """

    def test_create(self):
        """
        Ensure basic attributes when initialising the service
        """
        from gevent import pool

        my_service = make_service()

        self.assertFalse(my_service.started)
        self.assertEqual(my_service.services, [])
        self.assertIsInstance(my_service.pool, pool.Group)

    def test_get_logger(self):
        """
        A service should provide a logger as an attribute.
        """
        import logbook

        my_service = make_service()

        logger = my_service.logger

        self.assertIsInstance(logger, logbook.Logger)
        self.assertEqual(logger.name, 'Service')

    def test_get_logger_custom_name(self):
        """
        A service logger should be able to be named.
        """
        import logbook

        class MyService(service.Service):
            logger_name = 'my_log_name'

        my_service = MyService()

        logger = my_service.logger

        self.assertIsInstance(logger, logbook.Logger)
        self.assertEqual(logger.name, 'my_log_name')

    def test_start(self):
        """
        Ensure that starting a service works correctly.
        """
        my_service = SimpleService()

        self.event_fired = False

        def on_start():
            self.event_fired = True

        my_service.on('start', on_start)

        self.assertFalse(my_service.started)

        my_service.start()

        self.assertTrue(my_service.started)
        self.assertTrue(self.event_fired)

        # now test calling `start` again. It should be idempotent
        self.event_fired = False

        my_service.start()

        self.assertFalse(self.event_fired)

    @mock.patch.object(service.Service, 'do_start')
    def test_do_start(self, mock_do_start):
        """
        Ensure that do_start is called during `start`.
        """
        my_service = make_service()

        # Run something on service so it doesn't stop right away.
        my_service.spawn(gevent.sleep, 1)

        my_service.start()

        mock_do_start.assert_called_once_with()

        # ensure that `do_start` is called only once.
        my_service.start()

        mock_do_start.assert_called_once_with()

    def test_start_services(self):
        """
        Any greenlets in `service.services` must be `start`ed.
        """
        my_service = make_service(logger=mock.Mock())
        mock_greenlet = mock.Mock()

        my_service.add_service(mock_greenlet)

        my_service.join()

        mock_greenlet.join.assert_called_once_with()

    @mock.patch.object(service.Service, 'stop')
    def test_start_emit_error(self, mock_stop):
        """
        When a service is starting, the start event is emitted. If an exception
        occurs when emitting that event, the service must be torn down.
        """
        my_service = make_service(logger=mock.Mock())

        @my_service.on('start')
        def on_start():
            raise RuntimeError()

        with self.assertRaises(RuntimeError):
            my_service.start()

        self.assertTrue(mock_stop.called)

    @mock.patch.object(service.Service, 'teardown_service')
    def test_do_start_error(self, mock_teardown):
        """
        If an exception is raised when calling ``do_start`` while the service
        is starting, it must be torn down.
        """
        class MyService(service.Service):
            def do_start(self):
                raise RuntimeError

        my_service = MyService()
        my_service.logger = mock.Mock()

        with self.assertRaises(RuntimeError):
            my_service.start()

        mock_teardown.assert_called_once_with()

    def test_stop_not_started(self):
        """
        Can only `stop` a service when it has been started.
        """
        my_service = make_service()
        self.event_fired = False

        def on_stop():
            self.event_fired = True

        my_service.on('stop', on_stop)

        my_service.stop()

        self.assertFalse(self.event_fired)

    def test_stop(self):
        """
        Ensure that `stop`ping a service works correctly.
        """
        my_service = SimpleService()

        my_service.start()

        self.event_fired = False

        def on_stop():
            self.event_fired = True

        my_service.on('stop', on_stop)

        self.assertTrue(my_service.started)

        my_service.stop()

        self.assertFalse(my_service.started)
        self.assertTrue(self.event_fired)

        # now test calling `stop` again. It should be idempotent
        self.event_fired = False

        my_service.stop()

        self.assertFalse(self.event_fired)

    @mock.patch.object(service.Service, 'do_stop')
    def test_do_stop(self, mock_do_stop):
        """
        Ensure that `do_stop` is called during `stop`.
        """
        my_service = SimpleService()

        my_service.start()

        my_service.stop()

        mock_do_stop.assert_called_once_with()

        # ensure that `do_stop` is called only once.
        my_service.stop()

        mock_do_stop.assert_called_once_with()

    def test_stop_services(self):
        """
        Any greenlets in `service.services` must be `stop`ped.
        """
        my_service = SimpleService()
        my_service.start()

        mock_greenlet = mock.Mock()

        my_service.services = [mock_greenlet]

        my_service.stop()

        self.assertEqual(my_service.services, [])

        mock_greenlet.stop.assert_called_once_with()

    @mock.patch.object(service.Service, 'stop')
    @mock.patch.object(service.Service, 'start')
    def test_join(self, mock_start, mock_stop):
        """
        Ensure that `join` works as one would expect.
        """
        my_service = make_service()
        thread = my_service._run_thread = mock.Mock()

        my_service.join()

        mock_start.assert_called_once_with()
        thread.get.assert_called_once_with()
        mock_stop.assert_called_once_with()

    def test_spawn_error(self):
        """
        Spawning a greenlet that raises an exception must emit the error event
        via the service.
        """
        my_service = make_service()

        self.executed = False

        def trap_error(exc_type, exc_value, exc_traceback):
            self.assertIsInstance(exc_value, RuntimeError)
            self.executed = True

        def raise_error():
            raise RuntimeError

        my_service.on('error', trap_error)

        my_service.spawn(raise_error)

        gevent.sleep(0.0)

        self.assertTrue(self.executed)

    def test_spawn_exit(self):
        """
        Raising `gevent.GreenletExit` is not an error as such and the thread
        should exit correctly without emitting an `error` event.
        """
        my_service = make_service()

        self.executed = False

        def trap_error(exc_type, exc_value, exc_traceback):
            raise AssertionError('Whoops the error was trapped')

        def raise_error():
            self.executed = True
            raise gevent.GreenletExit

        my_service.on('error', trap_error)

        my_service.spawn(raise_error)

        gevent.sleep(0.0)

        self.assertTrue(self.executed)

    @mock.patch.object(service.Service, 'spawn')
    def test_add_service(self, mock_spawn):
        """
        Adding a child service when the parent service is stopped.
        """
        my_service = make_service()
        mock_service = mock.Mock()

        my_service.add_service(mock_service)

        self.assertFalse(mock_spawn.called)

        self.assertEqual(my_service.services, [mock_service])

    def test_service_error(self):
        """
        If a child service emits an error, the parent service must receive it.
        """
        child = make_service()
        parent = make_service()

        parent.add_service(child)

        self.executed = False

        @parent.on('error')
        def my_error(exc_type, exc_value, exc_tb):
            self.assertIs(exc_type, RuntimeError)
            self.assertIsInstance(exc_value, RuntimeError)
            self.assertIsNone(exc_tb)

            self.executed = True

        child.emit('error', RuntimeError())

        self.assertTrue(self.executed)

    @mock.patch.object(service.Service, 'watch_service')
    def test_add_service_start(self, mock_watch):
        """
        Adding a child service when the parent service is started.
        """
        mock_watch.__name__ = 'watch_service'

        my_service = SimpleService()
        mock_service = mock.Mock()

        my_service.start()

        my_service.add_service(mock_service)
        gevent.sleep(0.0)

        mock_watch.assert_called_once_with(mock_service)
        self.assertEqual(my_service.services, [mock_service])

    def test_teardown(self):
        """
        Teardown must be called before the state of the service is torn down.
        """
        class MyService(service.Service):
            def do_teardown(self):
                self.test.assertTrue(self.started)
                self.executed = True

        my_service = MyService()
        my_service.test = self

        my_service.start()
        my_service.stop()

        self.assertTrue(my_service.executed)

    def test_teardown_not_started(self):
        """
        Teardown must not be called if the service has not been started.
        """
        class MyService(service.Service):
            executed = False

            def do_teardown(self):
                self.executed = True

        my_service = MyService()

        my_service.stop()

        self.assertFalse(my_service.executed)

    def test_teardown_exception(self):
        """
        If there is an exception in `do_teardown`, the service must still be
        torn down.
        """
        self.executed = False

        class MyService(service.Service):
            def do_teardown(self):
                raise RuntimeError

        def check_error(exc_type, exc_value, exc_tb):
            self.assertIsInstance(exc_value, RuntimeError)
            self.executed = True

        my_service = MyService()
        mock_service = mock.Mock()

        my_service.add_service(mock_service)

        my_service.start()

        my_service.on('error', check_error)

        # stopping the service will not raise the exception but will dump it
        # to the logger
        my_service.stop()

        mock_service.stop.assert_called_once_with()
        self.assertTrue(self.executed)

    def test_no_greenlets_or_child_services(self):
        """
        If there are no greenlets spawned on the service or child services
        added, the service should start then immediately stop.
        """
        self.started = False
        self.stopped = False

        def start():
            self.started = True

        def stop():
            self.stopped = True

        class MyService(service.Service):
            def do_start(self):
                start()

            def do_stop(self):
                stop()

        my_service = MyService()

        my_service.start()

        gevent.sleep(0)

        self.assertTrue(self.started)
        self.assertTrue(self.stopped)
        self.assertFalse(my_service.started)

    def test_start_stop_simple_service(self):
        """
        If the service spawns a greenlet that runs forever, it should run until
        it is stopped.
        """
        self.executed = False

        def run(time):
            self.executed = True
            gevent.sleep(time)

        class MyService(service.Service):
            def do_start(self):
                self.spawn(run, 10)

        my_service = MyService()

        my_service.start()

        self.assertTrue(self.executed)
        self.assertTrue(my_service.started)

        my_service.stop()

        self.assertFalse(my_service.started)

    def test_start_stop_simple_service2(self):
        """
        If the service spawns a single greenlet, it should run until that
        greenlet has finished.
        """
        self.executed = False

        def run(time):
            self.executed = True
            gevent.sleep(time)

        class MyService(service.Service):
            def do_start(self):
                self.spawn(run, 0)

        my_service = MyService()

        my_service.start()

        self.assertTrue(self.executed)
        self.assertTrue(my_service.started)

        my_service.join()

        self.assertFalse(my_service.started)

    def test_start_stop_with_child_service(self):
        """
        If the service has a child service that runs forever, it should run
        until it is stopped.
        """
        self.executed = False

        def run(time):
            self.executed = True
            gevent.sleep(time)

        class ChildService(service.Service):
            def do_start(self):
                self.spawn(run, 10)

        my_service = make_service()
        child_service = ChildService()

        my_service.add_service(child_service)

        my_service.start()

        self.assertTrue(self.executed)
        self.assertTrue(my_service.started)
        self.assertTrue(child_service.started)

        my_service.stop()

        self.assertFalse(my_service.started)
        self.assertFalse(child_service.started)

    def test_start_stop_with_child_service2(self):
        """
        If the service has a single child service, it should run until that
        service has stopped.
        """
        self.executed = False

        def run(time):
            self.executed = True
            gevent.sleep(time)

        class ChildService(service.Service):
            def do_start(self):
                self.spawn(run, 0)

        my_service = make_service()
        child_service = ChildService()

        my_service.add_service(child_service)

        my_service.start()

        self.assertTrue(self.executed)
        self.assertTrue(my_service.started)
        self.assertTrue(child_service.started)

        my_service.join()

        self.assertFalse(my_service.started)
        self.assertFalse(child_service.started)

    def test_stopping_with_a_child_service(self):
        """
        Calling stop on a service that has a child service should not cause
        a `LoopExit` exception.
        """
        self.executed = [False, False]

        def run(index, time):
            self.executed[index] = True
            gevent.sleep(time)

        class MyService(service.Service):
            def do_start(self):
                self.spawn(run, 0, 0)

        class ChildService(service.Service):
            def do_start(self):
                self.spawn(run, 1, 10)

        my_service = MyService()
        child_service = ChildService()

        my_service.add_service(child_service)

        my_service.start()

        self.assertTrue(all(self.executed))
        self.assertTrue(my_service.started)
        self.assertTrue(child_service.started)

        my_service.stop()

    def test_stopping_with_a_child_service2(self):
        """
        A service that has a child service should be able to stop itself
        without causing a `LoopExit` exception.
        """
        self.executed = [False, False]

        def run(index, time):
            self.executed[index] = True
            gevent.sleep(time)

        class MyService(service.Service):
            def do_start(self):
                def run_and_stop():
                    run(0, 0)
                    gevent.spawn(self.stop)

                self.spawn(run_and_stop)

        class ChildService(service.Service):
            def do_start(self):
                self.spawn(run, 1, 10)

        my_service = MyService()
        child_service = ChildService()

        my_service.add_service(child_service)

        my_service.start()

        self.assertTrue(all(self.executed))
        self.assertTrue(my_service.started)
        self.assertTrue(child_service.started)

        my_service.join()


class ConfigurableServiceTestCase(unittest.TestCase):
    """
    Tests for `service.ConfigurableService`.
    """

    def test_create(self):
        """
        Create a configurable service.
        """
        from biloba import config

        my_service = service.ConfigurableService(None)

        self.assertIsInstance(my_service.config, config.Config)

    def test_default_config(self):
        """
        Test default config
        """
        class MyService(service.ConfigurableService):
            def get_config_defaults(self):
                return {'foo': 'bar'}

        my_service = MyService(None)

        self.assertEqual(my_service.config['foo'], 'bar')

    def test_override_default_config(self):
        class MyService(service.ConfigurableService):
            def get_config_defaults(self):
                return {'foo': 'bar'}

        my_service = MyService({'foo': 'baz'})

        self.assertEqual(my_service.config['foo'], 'baz')

    def test_biloba_config(self):
        """
        Supplying a :ref:`biloba.config.Config` must set that as the config
        instance for the service.
        """
        from biloba import config

        cfg = config.Config()

        svc = service.ConfigurableService(cfg)

        self.assertIs(svc.config, cfg)
