"""
Tests for `biloba.service`.
"""

import unittest
import mock

import gevent

from biloba import service


def make_service():
    return service.Service()


class ServiceTestCase(unittest.TestCase):
    """
    Tests for `service.Service`
    """

    def test_create(self):
        """
        Ensure basic attributes when initialising the service
        """
        my_service = make_service()

        self.assertFalse(my_service.started)
        self.assertEqual(my_service.services, [])
        self.assertEqual(my_service.spawned_greenlets, [])

    def test_delete(self):
        """
        Ensure stop is called when deleting the service.
        """
        my_service = make_service()

        with mock.patch.object(my_service, 'stop') as mock_stop:
            my_service.__del__()

            mock_stop.assert_called_once_with()

    def test_delete_error(self):
        """
        If `stop` causes an error while `__del__` is being called, swallow the
        exception.
        """
        my_service = make_service()

        with mock.patch.object(my_service, 'stop') as mock_stop:
            mock_stop.side_effect = RuntimeError

            my_service.__del__()

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

        my_service = make_service()

        my_service.logger_name = 'my_log_name'

        logger = my_service.logger

        self.assertIsInstance(logger, logbook.Logger)
        self.assertEqual(logger.name, 'my_log_name')

    def test_start(self):
        """
        Ensure that starting a service works correctly.
        """
        my_service = make_service()

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

    def test_do_start(self):
        """
        Ensure that do_start is called during `start`.
        """
        my_service = make_service()

        with mock.patch.object(my_service, 'do_start') as mock_do_start:
            my_service.start()

            mock_do_start.assert_called_one_with()

            # ensure that `do_start` is called only once.
            my_service.start()

            mock_do_start.assert_called_one_with()

    def test_start_services(self):
        """
        Any greenlets in `service.services` must be `start`ed.
        """
        my_service = make_service()
        mock_greenlet = mock.Mock()

        my_service.services = [mock_greenlet]

        my_service.start()

        mock_greenlet.start.assert_called_once_with()

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
        my_service = make_service()

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

    def test_do_stop(self):
        """
        Ensure that `do_stop` is called during `stop`.
        """
        my_service = make_service()

        my_service.start()

        with mock.patch.object(my_service, 'do_stop') as mock_do_stop:
            my_service.stop()

            mock_do_stop.assert_called_one_with()

            # ensure that `do_stop` is called only once.
            my_service.stop()

            mock_do_stop.assert_called_one_with()

    def test_stop_services(self):
        """
        Any greenlets in `service.services` must be `stop`ped.
        """
        my_service = make_service()
        my_service.start()

        mock_greenlet = mock.Mock()

        my_service.services = [mock_greenlet]

        my_service.stop()

        self.assertEqual(my_service.services, [])

        mock_greenlet.stop.assert_called_once_with()

    @mock.patch.object(service.Service, 'start')
    @mock.patch.object(service.Service, 'stop')
    def test_join(self, mock_stop, mock_start):
        """
        Ensure that `join` works as one would expect.
        """
        my_service = make_service()

        my_service.spawn(lambda: 'foobar')

        my_service.join()

        mock_start.assert_called_once_with()
        mock_stop.assert_called_with()

    def test_spawn(self):
        """
        Spawning a greenlet via the service allows for special things.
        """
        my_service = make_service()

        thread = my_service.spawn(lambda: [1, 2, 3])

        self.assertIn(thread, my_service.spawned_greenlets)

        # force a couple of context switches which allows the greenlet to be
        # cleaned up
        gevent.sleep(0.0)
        gevent.sleep(0.0)

        self.assertEqual(my_service.spawned_greenlets, [])

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

    def test_add_service(self):
        """
        Adding a child service when the parent service is stopped.
        """
        my_service = make_service()
        mock_service = mock.Mock()

        with mock.patch.object(my_service, 'spawn') as mock_spawn:
            my_service.add_service(mock_service)

            self.assertFalse(mock_spawn.called)

        self.assertEqual(my_service.services, [mock_service])

    def test_add_service_start(self):
        """
        Adding a child service when the parent service is started.
        """
        my_service = make_service()
        mock_service = mock.Mock()

        my_service.start()

        with mock.patch.object(my_service, 'spawn') as mock_spawn:
            my_service.add_service(mock_service)

            mock_spawn.assert_called_with(mock_service.join)

        self.assertEqual(my_service.services, [mock_service])

    def test_watch_service(self):
        """
        Ensure basic services do the right thing.
        """
        my_service = make_service()

        my_greenlet = gevent.spawn(lambda: 5)

        my_service.services = [my_greenlet]

        my_service.watch_services()

    def test_watch_service_error(self):
        """
        Error in a service.
        """
        my_service = make_service()
        service = mock.Mock()

        service.join.side_effect = RuntimeError

        my_service.services = [service]

        with self.assertRaises(RuntimeError):
            my_service.watch_services()


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
