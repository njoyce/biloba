import functools
import gevent
from gevent import event, pool
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
    :ivar logger: The logbook instance that is used by the service to log
        interesting events.
    """

    __slots__ = (
        'started',
        'services',
        'pool',
        'logger',
        '_run_thread',
        '_kill',
    )

    # set to specify the logger name (before the first access)
    logger_name = None

    def __init__(self, logger=None):
        super(Service, self).__init__()

        self.started = False
        self.services = []
        self.pool = pool.Group()
        self.logger = logger or self.get_logger()
        self._run_thread = None
        self._kill = event.Event()

    def get_logger(self):
        return logbook.Logger(self.logger_name or self.__class__.__name__)

    def do_start(self):
        """
        Called when this service is starting but before it is actually running.

        Create any child services or spawn greenlets here.
        """

    def do_stop(self):
        """
        Called when this service is stopped. Any child services that have been
        added to this service will have already been stopped.

        The thread pool will also have been cleaned up.

        Perform any necessary cleanup.
        """

    def do_teardown(self):
        """
        Called when this service is being torn down. This is different to
        `stop` in that this will be called before any state has been torn down.
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
            # Finish service if everything in the pool is done.
            def finish():
                self.pool.join()

                if not self._kill.is_set():
                    self._kill.set()

            # there is no running thread, let's start it
            def run():
                with self.emit_exceptions(propagate=False):
                    try:
                        self.start_service()

                        gevent.spawn(finish)

                        self._kill.wait()
                    finally:
                        self.stop_service()

            self._run_thread = gevent.spawn(run)

            # ensure that the _run_thread attribute is cleaned up when the
            # greenlet comes to an end
            def cleanup(g):
                self._run_thread = None

            self._run_thread.rawlink(cleanup)

        if not block:
            return

        # block this greenlet until the run thread starts the service
        result = gevent.event.AsyncResult()

        @self.once('error')
        def on_error(*exc_info):
            self.remove_listener('start', on_start)

            result.set(exc_info)

        @self.once('start')
        def on_start():
            self.remove_listener('error', on_error)

            result.set()

        exc_info = result.get()

        if exc_info:
            raise exc_info[0], exc_info[1], exc_info[2]

    def stop(self, block=True):
        """
        Called to stop this service if it is running. All child services are
        `stopped` and any greenlets this service may have spawned are killed.

        Any custom code should generally go in to `do_stop`.
        """
        if not self.started:
            return

        self._kill.set()

        if block:
            try:
                self._run_thread.get()
            except gevent.GreenletExit:
                pass

    def start_service(self):
        """
        Called in the running service thread to start the service. This method
        blocks until all the child services have started.
        """
        self.do_start()

        for child in self.services:
            child.start(block=True)

            self.spawn(self.watch_service, child)

        self.started = True

        try:
            self.emit('start')
        except:
            self.stop()

            raise

    def stop_service(self):
        try:
            self.teardown_service()
        finally:
            try:
                self.do_stop()
            finally:
                self.started = False

                # it is important that everything is torn down before the
                # event is emitted
                self.emit('stop')

    def teardown_service(self):
        """
        Stop all services and kill any spawned greenlets.

        This is generally an internally called method, use with care.
        """
        try:
            self.do_teardown()
        finally:
            for service in self.services:
                service.stop()

            self.services = []
            self.pool.kill()

    def join(self):
        """
        Called to block the current greenlet to wait for this service to finish
        """
        # start is idempotent
        self.start()

        try:
            self._run_thread.get()
        finally:
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

    def spawn(self, func, *args, **kwargs):
        """
        Spawns a greenlet that is linked to this service and will be killed if
        the service stops.

        :param func: The callable to execute in a new greenlet context.
        :param args: The args to pass to the callable.
        :param kwargs: The kwargs to pass to the callable.
        :returns: The spawned greenlet thread.
        """
        @functools.wraps(func)
        def wrapped():
            with self.emit_exceptions(propagate=False):
                return func(*args, **kwargs)

        return self.pool.spawn(wrapped)

    def watch_service(self, child):
        """
        Watch a child service and if it returns, this service is done.
        """
        try:
            child.join()
        finally:
            if not self._kill.is_set():
                self._kill.set()


class ConfigurableService(Service):
    """
    A service that takes a config dict
    """

    __slots__ = (
        'config',
    )

    def __init__(self, config, logger=None):
        """
        :param config: Provide a dict like interface
        """
        config = self.apply_default_config(config or {})

        if isinstance(config, biloba_config.Config):
            self.config = config
        else:
            self.config = biloba_config.Config(config)

        super(ConfigurableService, self).__init__(logger=logger)

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
