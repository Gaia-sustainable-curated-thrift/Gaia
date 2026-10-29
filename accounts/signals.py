from django.db.models.signals import post_delete
from django.dispatch import receiver
from .avatars import schedule_avatar_delete
from .models import Profile


@receiver(post_delete, sender=Profile)
def remove_profile_avatar(sender, instance, **kwargs):
    schedule_avatar_delete(instance.avatar)
