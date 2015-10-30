import asyncio

import aiopg
import aioredis
from aiohttp import web

from settings import SERVER, DB, REDIS
from views import PrivateMessageHandler


dsn = 'dbname={NAME} user={USER} password={PASSWORD} host={HOST}'.format(**DB)
redis_address = (REDIS['HOST'], REDIS['PORT'])


@asyncio.coroutine
def init(loop):
    app = web.Application(loop=loop)

    # -------------------------------------------------------------------------

    app.router.add_route(
        'GET', r'/{thread_id:\d+}/{user_id:\d+}/', PrivateMessageHandler()
    )

    # -------------------------------------------------------------------------

    app['pg_pool'] = yield from aiopg.create_pool(dsn)
    app['redis_pool'] = yield from aioredis.create_pool(redis_address)

    # -------------------------------------------------------------------------

    srv = yield from loop.create_server(
        app.make_handler(), SERVER['HOST'], SERVER['PORT']
    )
    print(
        "Server started at http://{0}:{1}".format(
            SERVER['HOST'], SERVER['PORT']
        )
    )

    return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))

try:
    loop.run_forever()
except KeyboardInterrupt:
    pass
