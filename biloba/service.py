import functools
import sys

import gevent
import logbook
import pyee

from . import util, config as biloba_config


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

    __slots__ = (
        'started',
        'services',
        'spawned_greenlets',
        'logger',
    )

    def __init__(self):
        super(Service, self).__init__()

        self.started = False
        self.services = []
        self.spawned_greenlets = []

    def __del__(self):
        try:
            self.stop()
        except:
            pass

    @util.cachedproperty
    def logger(self):
        return self.get_logger()

    # set to specify the logger name (before the first access)
    logger_name = None

    def get_logger(self):
        return logbook.Logger(self.logger_name or self.__class__.__name__)

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
        """
        # start is idempotent
        self.start()

        # all `spawned` greenlets are `link`ed to `remove_greenlet` which means
        # that when `joinall` returns all of the greenlets that were passed in
        # will have been removed from the `spawned_greenlets` list - however,
        # those greenlets may have spawned more greenlets.
        while self.spawned_greenlets:
            gevent.joinall(self.spawned_greenlets)

        self.stop()

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
        except ValueError:
            pass

    def spawn(self, func, *args, **kwargs):
        """
        Spawns a greenlet that is linked to this service and will be killed if
        the service stops.

        :param func: The callable to execute in a new greenlet context.
        :param args: The args to pass to the callable.
        :param kwargs: The kwargs to pass to the callable.
        :returns: The spawned greenlet thread.
        """
        def log_exc(func):
            """
            Log any exceptions as they happen from the function being spawned.
            """
            @functools.wraps(func)
            def wrapper(*args, **kwargs):  # pylint: disable=C0111
                try:
                    return func(*args, **kwargs)
                except gevent.GreenletExit:
                    raise
                except:
                    self.emit('error', *sys.exc_info())

            return wrapper

        thread = gevent.spawn(log_exc(func), *args, **kwargs)

        self.spawned_greenlets.append(thread)

        thread.rawlink(self.remove_greenlet)

        return thread

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

        for thread in greenlets:
            thread.kill()

        if ret.exception:
            raise ret.exception.__class__, ret.exception, None


class ConfigurableService(Service):
    """
    A service that takes a config dict
    """

    __slots__ = (
        'config',
    )

    def __init__(self, config):
        """
        :param config: Provide a dict like interface
        """
        super(ConfigurableService, self).__init__()

        config = self.apply_default_config(config or {})

        self.config = biloba_config.Config(config)

    def get_config_defaults(self):
        return {}

    def apply_default_config(self, config):
        defaults = self.get_config_defaults()

        for key, value in defaults.items():
            config.setdefault(key, value)

        return config
