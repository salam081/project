from django.db import models
from accounts.models import Member,User

class SavingType(models.Model):
    title = models.CharField(max_length=50)
    request_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    available = models.BooleanField(default=True)
    
    def __str__(self):
        return self.title
class SpecialSavingsTergetSavingsRequestForm(models.Model):
    STATUS_CHOICES = (("paid", "Paid"),  ("used", "Used"))
    member = models.ForeignKey("accounts.Member", on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    savings_type = models.ForeignKey(SavingType, on_delete=models.CASCADE) #,related_name="special_saving_type"
    form_fee = models.DecimalField(max_digits=10, decimal_places=2)
    duration_in_months = models.IntegerField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="paid")
    date_created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["-date_created"]

    def __str__(self):
        return f"{self.member} " 
    
    
class SpecialSavings(models.Model):
    member = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="special_savings")
    month = models.DateField(db_index=True)
    month_savings = models.DecimalField(max_digits=10, decimal_places=2)
    date_created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ("member", "month")
        indexes = [
            models.Index(fields=["member", "month"]),
        ]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.member.update_special_savings()


    def __str__(self):
        return f"{self.member} - {self.month.strftime('%B %Y')}: ₦{self.month_savings}"



class TargetSavings(models.Model):
    member = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="target_savings")
    month = models.DateField(db_index=True)
    month_savings = models.DecimalField(max_digits=10, decimal_places=2)
    date_created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ("member", "month")
        indexes = [
            models.Index(fields=["member", "month"]),
        ]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.member.update_target_savings()


    def __str__(self):
        return f"{self.member} - {self.month.strftime('%B %Y')}: ₦{self.month_savings}"



   