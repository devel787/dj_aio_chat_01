from django.conf.urls import url

from .views import (
    send_message_view, send_message_api_view, chat_view, messages_view,
)


urlpatterns = [
    url(r'^$', messages_view, name='messages_view'),

    url(r'^(?P<thread_id>\d+)/$', chat_view, name='chat_view'),

    url(r'^send_message/$', send_message_view, name='send_message_view'),

    url(
        r'^send_message_api/(?P<thread_id>\d+)/$',
        send_message_api_view,
        name='send_message_api_view'
    ),
]
