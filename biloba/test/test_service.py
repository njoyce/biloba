"""
Tests for `biloba.service`.
"""

import unittest
import mock

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
