from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Savings


@receiver(post_save, sender=Savings)
def update_savings_on_save(sender, instance, **kwargs):
    """
    Update member's total_savings whenever a Saving is created or updated.
    """
    instance.member.update_total_savings()


@receiver(post_delete, sender=Savings)
def update_savings_on_delete(sender, instance, **kwargs):
    """
    Update member's total_savings whenever a Saving is deleted.
    """
    instance.member.update_total_savings()
