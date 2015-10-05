from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Thread, Message


@receiver(post_save, sender=Message, dispatch_uid='Message.post_save.uid')
def update_last_message_datetime(sender, instance, created, **kwargs):
    """
    Update Thread's last_message field when a new message is sent.
    """
    if created:
        (
            Thread.objects
            .filter(id=instance.thread.id)
            .update(last_message=instance.datetime)
        )
