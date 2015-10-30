import time
import json
import asyncio

import aiohttp
from aiohttp import web

from settings import API_KEY, SEND_MESSAGE_API_URL


class PrivateMessageHandler:
    @asyncio.coroutine
    def __call__(self, request):
        yield from self.validation_part(request)

        ws = web.WebSocketResponse()
        yield from ws.prepare(request)

        pub = yield from request.app['redis_pool'].acquire()
        sub = yield from request.app['redis_pool'].acquire()

        channel = 'thread_{0}_messages'.format(self.thread_id)

        sub_channel_list = yield from sub.subscribe(channel)
        zero_sub_channel = sub_channel_list[0]

        # Kick off both coroutines in parallel,
        # and then block until both are completed.
        yield from asyncio.gather(
            self.handle_ws_part(ws, pub, channel),
            self.handle_redis_part(ws, zero_sub_channel)
        )

        return ws

    @asyncio.coroutine
    def validation_part(self, request):
        self.user_id = request.match_info.get('user_id')

        with (yield from request.app['pg_pool'].cursor()) as cur:
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

        with (yield from request.app['pg_pool'].cursor()) as cur:
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
        while not ws.closed:
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
                        SEND_MESSAGE_API_URL, self.thread_id
                    )
                    payload = {
                        'message': msg.data,
                        'api_key': API_KEY,
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
