from django.db.models.signals import post_delete, pre_save
from django.contrib.auth import get_user_model
from django.dispatch import receiver
from .avatars import schedule_avatar_delete
from .models import Profile


@receiver(post_delete, sender=Profile)
def remove_profile_avatar(sender, instance, **kwargs):
    schedule_avatar_delete(instance.avatar)


@receiver(pre_save, sender=get_user_model())
def revoke_mobile_tokens_on_password_change(sender, instance, **kwargs):
    if instance.pk:
        previous = sender.objects.filter(pk=instance.pk).values_list('password', flat=True).first()
        if previous is not None and previous != instance.password:
            from rest_framework.authtoken.models import Token
            Token.objects.filter(user_id=instance.pk).delete()
