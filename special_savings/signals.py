from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import SpecialSavings, TargetSavings


@receiver(post_save, sender=SpecialSavings)
def update_special_savings_on_save(sender, instance, **kwargs):
    """
    Update member's total_special_savings whenever a SpecialSaving is created or updated.
    """
    instance.member.update_special_savings()


@receiver(post_delete, sender=SpecialSavings)
def update_special_savings_on_delete(sender, instance, **kwargs):
    """
    Update member's total_special_savings whenever a SpecialSaving is deleted.
    """
    instance.member.update_special_savings()


# ============= target savings signals ================

@receiver(post_save, sender=TargetSavings)
def update_target_savings_on_save(sender, instance, created, **kwargs):
    # Only recalc when new record is created
    if created:
        instance.member.update_target_savings()


@receiver(post_delete, sender=TargetSavings)
def update_target_savings_on_delete(sender, instance, **kwargs):
    instance.member.update_target_savings()
