from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Order, UserProfile

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)


@receiver(post_save, sender=Order)
def notify_order_update(sender, instance, created, **kwargs):
    if not instance.user or not instance.user.email:
        return
    subject = f"WaterSupply Order #{instance.id} Update"
    if created:
        message = (
            f"Your order #{instance.id} has been placed.\n"
            f"Total: Rs. {instance.total_amount}\n"
            f"Status: {instance.get_tracking_status_display()}\n"
        )
    else:
        message = (
            f"Your order #{instance.id} is now {instance.get_tracking_status_display()}.\n"
            f"Payment: {instance.get_payment_status_display()}\n"
        )
    send_mail(
        subject=subject,
        message=message,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@watersupply.local"),
        recipient_list=[instance.user.email],
        fail_silently=True,
    )
