import gevent.pool
import logbook

from . import config as biloba_config, events


class Service(events.EventEmitter):
    """
    An asynchronous primitive that will maintain a pool of spawned greenlets
    and watch any child services (which are just objects the same as this).

    The service will wait until all children greenlets have completed. All
    exceptions raised by child services will bubble up to this service.

    There is a distinction between arbitrary greenlets and 'service' greenlets.
    A service greenlet is meant to run forever, if for some reason it dies
    early then all other services are torn down as this parent service is done.

    All greenlets that are spawned by this service are specially managed. If
    the greenlet throws an exception, the 'error' event will be emitted by this
    service.

    :ivar started: Whether this service has started.
    :type started: Boolean.
    :ivar services: A list of child service objects that this service is
        watching.
    :ivar pool: A thread pool controlled by this service. If the threadpool
        empties, this service is dead.
    """

    __slots__ = (
        'started',
        'services',
        'pool',
        'logger',
        '_run_thread',
    )

    # set to specify the logger name (before the first access)
    logger_name = None

    def __init__(self):
        super(Service, self).__init__()

        self.started = False
        self.services = []
        self.pool = gevent.pool.Group()
        self.logger = self.get_logger()
        self._run_thread = None

    def get_logger(self):
        return logbook.Logger(self.logger_name or self.__class__.__name__)

    def do_start(self):
        """
        Called when this service is starting but before it is actually running.

        Create any child services or spawn greenlets here.
        """

    def do_stop(self):
        """
        Called when this service is stopping. Any child services that have been
        added to this service will have already been stopped.

        The thread pool will also have been cleaned up.

        Perform any necessary cleanup.
        """

    def start(self, block=True):
        """
        Called to start this service and any child services that may be
        registered.

        Any custom code should generally go in to `do_start`.
        """
        if self.started:
            return

        if not self._run_thread:
            self._run_thread = gevent.spawn(self._run)

        if not block:
            return

        result = gevent.event.AsyncResult()

        @self.once('error')
        def on_error(*exc_info):
            result.set_exception(exc_info[1])
            self.remove_listener('start', on_start)

        @self.once('start')
        def on_start():
            result.set()
            self.remove_listener('error', on_error)

        result.wait()

    def _run(self):
        try:
            with self.emit_exceptions(propagate=False):
                try:
                    self.do_start()

                    for child in self.services:
                        self.spawn(self.watch_service, child)
                    # TODO - wait for the child services to all start
                except:
                    self.teardown()

                    raise

                self.started = True

                try:
                    self.emit('start')
                except:
                    self.stop()

                    raise

                self.pool.join()
        finally:
            with self.emit_exceptions(propagate=False):
                try:
                    self.teardown()
                    self.do_stop()
                finally:
                    self._run_thread = None
                    self.started = False

                    # it is important that everything is torn down before the
                    # event is emitted
                    self.emit('stop')

    def teardown(self):
        """
        Stop all services and kill any spawned greenlets.

        This is generally an internally called method, use with care.
        """
        for service in self.services:
            service.stop()

        self.services = []
        self.pool.kill()

    def stop(self, block=True):
        """
        Called to stop this service if it is running. All child services are
        `stopped` and any greenlets this service may have spawned are killed.

        Any custom code should generally go in to `do_stop`.
        """
        if not self.started:
            return

        # stop is callable from any greenlet
        if self._run_thread:
            if self._run_thread.dead:
                return

            self._run_thread.kill(block=block)

    def join(self):
        """
        Called to block the current greenlet to wait for this service to finish
        """
        # start is idempotent
        self.start()

        self.pool.join()

        self.stop()

    def handle_service_error(self, service, *exc_info):
        """
        Called when a service that this parent is watching emits an 'error'
        event.

        The default behaviour is to emit the exception in the context of this
        service.

        :param service: The service object that emitted the error.
        :param exc_info: The exception tuple as returned by ``sys.exc_info()``.
        """
        self.emit('error', *exc_info)

    def add_service(self, *services):
        """
        Add a service to this parent service object. A service must only have
        one parent.
        """
        for child in services:
            # push all child errors in to the error handling mechanism of this
            # service
            child.on(
                'error',
                lambda *exc_info: self.handle_service_error(child, *exc_info)
            )

        self.services.extend(services)

        if not self.started:
            return

        for child in services:
            self.spawn(self.watch_service, child)

    def emit_exceptions(self, propagate=True, always_log=False, emit=True):
        """
        Returns a context manager that will log exceptions that are not handled
        when the ``error`` event is emitted.

        :param propagate: Propagate all exceptions (i.e. re-raise).
        :param always_log: Whether to log the exception even if handled.
        :param emit: Whether to emit the `error` event if an exception is
            trapped.
        """
        return events.emit_exceptions(
            self,
            self.logger,
            propagate=propagate,
            always_log=always_log,
            emit=emit,
            skip_types=(gevent.GreenletExit,),
        )

    def exec_func(self, func, *args, **kwargs):
        """
        Execute the function and emit an error if an exception occurs. If
        the error is not trapped/handled, the default behaviour is to
        output the exception to the logger.

        :param func: The function to execute.
        :param args: The params to pass to `func`.
        :param kwargs: The keyword arguments to pass to `func`.
        """
        with self.emit_exceptions(propagate=False):
            return func(*args, **kwargs)

    def spawn(self, func, *args, **kwargs):
        """
        Spawns a greenlet that is linked to this service and will be killed if
        the service stops.

        :param func: The callable to execute in a new greenlet context.
        :param args: The args to pass to the callable.
        :param kwargs: The kwargs to pass to the callable.
        :returns: The spawned greenlet thread.
        """
        return self.pool.spawn(self.exec_func, func, *args, **kwargs)

    def watch_service(self, child):
        """
        Watch a child service and if it returns, this service is done.
        """
        try:
            child.join()
            self.logger.debug('{!r} completed'.format(child))
        finally:
            self.teardown()


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
        config = self.apply_default_config(config or {})

        self.config = biloba_config.Config(config)

        super(ConfigurableService, self).__init__()

    def get_config_defaults(self):
        """
        Return a dict that will hold the default config (if any) for this
        service.
        """
        return {}

    def apply_default_config(self, config):
        defaults = self.get_config_defaults()

        for key, value in defaults.items():
            config.setdefault(key, value)

        return config
