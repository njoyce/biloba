Biloba
======

As in Ginkgo (of which this module was inspired). Provides gevent primitives to
orchestrate different orthogonal servers and services together.

Basic usage::

    from gevent import wsgi

    import biloba

    
    def hello_world(environ, start_response):
        start_response('200 OK', [('Content-Type', 'text/html')])

        return ['<b>Hello world!</b>\n']


    class MyService(biloba.Service):
        def make_web_server(self):
            return wsgi.WSGIServer(
                ('localhost', 5000),
                hello_world
            )

        def do_start(self):
            self.web_server = self.make_web_server()

            self.spawn(self.web_server.serve_forever)
            
            # you can add more servers/services here


    if __name__ == '__main__':
        my_service = MyService()

        # start is called by join

        try:
            my_service.join()
        except KeyboardInterrupt:
            pass

        # as is stop
