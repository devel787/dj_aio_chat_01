from django.apps import AppConfig


class PrivateMessagesConfig(AppConfig):
    name = 'privatemessages'

    def ready(self):
        from . import signals
