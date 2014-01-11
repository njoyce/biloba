import functools

import gevent
import logbook
import pyee

from . import util


class Service(pyee.EventEmitter):
    """
    An asynchronous primitive that will maintain a pool of spawned greenlets
    and watch any child services (which are just objects the same as this).

    The service will wait until all children greenlets have completed.

    There is a distinction between arbitrary greenlets and 'service' greenlets.
    A service greenlet is meant to run forever, if for some reason it dies
    early then all other services are torn down as this parent service is done.

    :ivar started: Whether this service has started.
    :type started: Boolean.
    :ivar services: A list of child service objects that this service is
        watching.
    :ivar spawned_greenlets: A list of greenlets that is being watched by this
        service.
    """

    def __init__(self):
        super(Service, self).__init__()

        self.started = False
        self.services = []
        self.spawned_greenlets = []
        self._logger = None

    @util.cachedproperty
    def logger(self):
        return self.get_logger()

    def get_logger(self):
        return logbook.Logger(self.__class__.__name__)

    def add_service(self, *services):
        """
        Add a service to this parent service object. A child service must only
        have one parent
        """
        self.services.extend(services)

        if not self.started:
            return

        for service in services:
            self.spawn(service.join)

    def remove_greenlet(self, g):
        try:
            self.spawned_greenlets.remove(g)
        except:
            pass

    def spawn(self, func, *args, **kwargs):
        """
        Spawns a greenlet that is linked to this service and will be killed if
        the service stops.
        """
        def log_exc(func):
            """
            Log any exceptions as they happen from the function being spawned.
            """
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    self.logger.exception(
                        '{}(*{!r}), **{!r})'.format(func, args, kwargs)
                    )

                    self.emit('error', e)

                    raise

            return wrapper

        g = gevent.spawn(log_exc(func), *args, **kwargs)

        self.spawned_greenlets.append(g)

        g.link(lambda g: self.remove_greenlet(g))

        return g

    def do_start(self):
        """
        Called when this service is starting but before it is actually running.

        Create any child services or spawn greenlets here.
        """

    def do_stop(self):
        """
        Called when this service is stopping.

        Perform any necessary cleanup.
        """

    def start(self):
        """
        Called to start this service and any child services that may be
        registered.

        Any custom code should generally go in to `do_start`.
        """
        if self.started:
            return

        self.do_start()

        for service in self.services:
            service.start()

        self.spawn(self.watch_services)

        self.started = True

        self.emit('start')

    def stop(self):
        """
        Called to stop this service if it is running. All child services are
        `stopped` and any greenlets this service may have spawned are killed.

        Any custom code should generally go in to `do_stop`.
        """
        if not self.started:
            return

        try:
            for service in self.services:
                service.stop()

            for g in self.spawned_greenlets:
                if not g.dead:
                    g.kill()

            self.services = []
            self.spawned_greenlets = []

            self.do_stop()
        finally:
            self.started = False
            self.emit('stop')

    def join(self):
        """
        Called to block the current greenlet to wait for this service to finish

        It is the job of the parent greenlet to call `stop`.
        """
        if not self.started:
            self.start()

        # all `spawned` greenlets are `link`ed to `remove_greenlet` which means
        # that when `joinall` returns all of the greenlets that were passed in
        # will have been removed from the `spawned_greenlets` list - however,
        # those greenlets may have spawned more greenlets.
        while self.spawned_greenlets:
            gevent.joinall(self.spawned_greenlets)

    def watch_services(self):
        # `self.spawn` is not used because we don't use want to kill these
        # immediately, see below
        greenlets = [gevent.spawn(s.join) for s in self.services]

        if not greenlets:
            return

        # a service greenlet is never supposed to exit, so if one does then
        # the parent service has ended and any calls to `join` must exit.
        ret = util.waitany(greenlets)

        greenlets.remove(ret)

        for g in greenlets:
            g.kill()

        if ret.exception:
            self.emit('error', ret.exception)

            raise ret.exception


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

    def __init__(self, config):
        self.config = config

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
        value = util.get_config_key(self.config, key, default=default)

        return self.expand(value)


class ConfigurableService(Service):
    """
    A service that takes a config dict
    """

    def __init__(self, config):
        """
        :param config: Provide a dict like interface
        """
        super(ConfigurableService, self).__init__()

        self.config = Config(config)

        self.apply_default_config()

    def get_logger(self):
        logger = super(ConfigurableService, self).get_logger()

        sentry_dsn = self.config.get('SENTRY_DSN')

        if not sentry_dsn:
            return logger

        return install_raven(logger, sentry_dsn)

    def get_config_defaults(self):
        return {}

    def apply_default_config(self):
        defaults = self.get_config_defaults()

        for key, value in defaults.items():
            self.config.setdefault(key, value)


def install_raven(logger, sentry_dsn):
    try:
        from raven.handlers.logbook import SentryHandler
    except ImportError:
        return logger

    handler = SentryHandler(sentry_dsn, bubble=True)

    logger.handlers.append(handler)

    return logger


def run(service):
    """
    Helper function to start, join and stop a service.
    """
    service.start()

    try:
        service.join()
    finally:
        service.stop()
