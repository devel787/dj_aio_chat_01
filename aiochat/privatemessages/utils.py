import json
import redis

from django.http import JsonResponse
from django.utils import dateformat

from .models import Message


class BadJsonResponse(JsonResponse):
    status_code = 400


def send_message(thread_id, sender_id, message_text, sender_name=None):
    """
    This function takes Thread object id (first argument),
    sender id (second argument), message text (third argument)
    and can also take sender's name.

    It creates a new Message object and increases the
    values stored in Redis that represent the total number
    of messages for the thread and the number of this thread's
    messages sent from this specific user.

    If a sender's name is passed, it also publishes
    the message in the thread's channel in Redis
    (otherwise it is assumed that the message was
    already published in the channel).
    """

    message = Message.objects.create(
        text=message_text, thread_id=thread_id, sender_id=sender_id
    )

    if sender_name:
        r = redis.StrictRedis()

        r.publish(
            'thread_{0}_messages'.format(thread_id),
            json.dumps(
                {
                    'timestamp': dateformat.format(message.datetime, 'U'),
                    'sender': sender_name,
                    'text': message_text,
                }
            )
        )
