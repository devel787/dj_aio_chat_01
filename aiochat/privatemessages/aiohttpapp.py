import time
import json
import asyncio
import traceback
from importlib import import_module

from django.conf import settings

import aiohttp
import aiopg
import aioredis
from aiohttp import web


session_engine = import_module(settings.SESSION_ENGINE)

dsn = 'dbname={NAME} user={USER} password={PASSWORD} host={HOST}'.format(
    **settings.DATABASES['default']
)
redis_address = ('localhost', 6379)


class PrivateMessageHandler:
    @asyncio.coroutine
    def __call__(self, request):
        yield from self.validation_part(request)

        ws = web.WebSocketResponse()
        ws.start(request)

        pub = yield from aioredis.create_redis(redis_address)
        sub = yield from aioredis.create_redis(redis_address)

        channel = 'thread_{0}_messages'.format(self.thread_id)

        sub_channel_list = yield from sub.subscribe(channel)
        zero_sub_channel = sub_channel_list[0]

        # ---------------------------------------------------------------------

        print('Connection opened')

        try:
            # Kick off both coroutines in parallel,
            # and then block until both are completed.
            yield from asyncio.gather(
                self.handle_ws_part(ws, pub, channel),
                self.handle_redis_part(ws, zero_sub_channel)
            )
        except Exception:
            print('')
            print('except Exception:')
            print('--------------------------------')
            traceback.print_exc()
            print('--------------------------------')
        finally:
            sub.close()
            pub.close()
            print('Connection closed')

        return ws

    @asyncio.coroutine
    def validation_part(self, request):
        session_key = request.cookies.get(settings.SESSION_COOKIE_NAME)
        session = session_engine.SessionStore(session_key)

        try:
            self.user_id = session['_auth_user_id']
        except KeyError:
            raise aiohttp.web.HTTPBadRequest(reason='KeyError')

        pool = yield from aiopg.create_pool(dsn)
        with (yield from pool.cursor()) as cur:
            yield from cur.execute(
                'SELECT username FROM auth_user WHERE id = %s',
                (self.user_id, )
            )
            sql_res = yield from cur.fetchone()

            if sql_res is None:
                raise aiohttp.web.HTTPBadRequest(reason='Wrong user_id')

            self.sender_name = sql_res[0]

        # ---------------------------------------------------------------------

        self.thread_id = request.match_info.get('thread_id')

        pool = yield from aiopg.create_pool(dsn)
        with (yield from pool.cursor()) as cur:
            yield from cur.execute(
                """
                SELECT pt.id FROM privatemessages_thread AS pt
                INNER JOIN privatemessages_thread_participants AS ptp
                ON (pt.id = ptp.thread_id)
                WHERE (pt.id = %s AND ptp.user_id = %s)
                """,
                (self.thread_id, self.user_id)
            )
            sql_res = yield from cur.fetchone()

            if sql_res is None:
                raise aiohttp.web.HTTPBadRequest(reason='Wrong thread_id')

    @asyncio.coroutine
    def handle_ws_part(self, ws, pub, channel):
        while True:
            msg = yield from ws.receive()

            if msg.tp == aiohttp.MsgType.text:
                if msg.data != 'close':
                    json_msg = json.dumps({
                        'timestamp': time.time(),
                        'sender': self.sender_name,
                        'text': msg.data
                    })
                    yield from pub.publish_json(channel, json_msg)

                    post_url = '{0}/{1}/'.format(
                        settings.SEND_MESSAGE_API_URL, self.thread_id
                    )
                    payload = {
                        'message': msg.data,
                        'api_key': settings.API_KEY,
                        'sender_id': self.user_id
                    }
                    response = yield from aiohttp.post(post_url, data=payload)
                    assert response.status == 200
                else:
                    yield from ws.close()
            elif msg.tp == aiohttp.MsgType.close:
                print('ws connection closed')
            elif msg.tp == aiohttp.MsgType.error:
                print('ws connection exception {0}'.format(ws.exception()))

    @asyncio.coroutine
    def handle_redis_part(self, ws, channel):
        while (yield from channel.wait_message()):
            msg = yield from channel.get_json()
            ws.send_str(msg)

    def __init__(self):
        self.user_id = None
        self.sender_name = None
        self.thread_id = None
