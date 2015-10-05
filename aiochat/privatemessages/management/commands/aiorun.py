import asyncio

from aiohttp import web

from django.core.management.base import BaseCommand, CommandError

from privatemessages.aiohttpapp import PrivateMessageHandler


class Command(BaseCommand):
    args = '[port_number]'
    help = 'Starts the aiohttp application for message handling.'

    def handle(self, *args, **options):
        if len(args) == 1:
            try:
                port = int(args[0])
            except ValueError:
                raise CommandError('Invalid port number specified')
        else:
            port = 8888

        # ---------------------------------------------------------------------

        app = web.Application()
        app.router.add_route('GET', '/{thread_id}/', PrivateMessageHandler())

        loop = asyncio.get_event_loop()
        handler = app.make_handler()

        f = loop.create_server(handler, '127.0.0.1', port)
        srv = loop.run_until_complete(f)

        self.stdout.write('serving on {0}'.format(srv.sockets[0].getsockname()))

        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            loop.run_until_complete(handler.finish_connections(1.0))
            srv.close()
            loop.run_until_complete(srv.wait_closed())
            loop.run_until_complete(app.finish())
        loop.close()
