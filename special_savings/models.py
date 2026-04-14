from django.db import models
from pytz import timezone
from django.utils import timezone
from django.db import transaction

from django.utils import timezone
from django.db import transaction

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
    created_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["-date_created"]

    def __str__(self):
        return f"{self.member} " 
    
    
class SpecialSavings(models.Model):
    member = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="special_savings")
    month = models.DateField(db_index=True)
    month_savings = models.DecimalField(max_digits=10, decimal_places=2)
    date_created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True)

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
    created_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, blank=True)

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




class TargetSavingsWithdrawal(models.Model):

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    member = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="target_savings_withdrawals")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField(blank=True, null=True)
    status = models.CharField( max_length=20, choices=STATUS_CHOICES, default='pending')
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey("accounts.User",on_delete=models.SET_NULL,null=True,blank=True)

    def __str__(self):
        return f"{self.member} - ₦{self.amount} ({self.status})"


    def approve(self, reviewed_by):
        """Approve withdrawal and deduct from member target savings"""

        if self.status != "pending":
            raise ValueError("Only pending withdrawals can be approved.")

        if self.amount > self.member.total_target_savings:
            raise ValueError("Withdrawal amount exceeds available target savings.")

        with transaction.atomic():

            self.status = "approved"
            self.reviewed_by = reviewed_by
            self.reviewed_at = timezone.now()
            self.save()

            member = self.member
            member.total_target_savings -= self.amount
            member.save(update_fields=["total_target_savings"])


    def reject(self, reviewed_by):
        """Reject withdrawal"""

        if self.status != "pending":
            raise ValueError("Only pending withdrawals can be rejected.")

        self.status = "rejected"
        self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now()
        self.save()
        
        
class SpecialSavingsWithdrawal(models.Model):

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    member = models.ForeignKey("accounts.Member", on_delete=models.CASCADE, related_name="special_savings_withdrawals")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField(blank=True, null=True)
    status = models.CharField( max_length=20, choices=STATUS_CHOICES, default='pending')
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey("accounts.User",on_delete=models.SET_NULL,null=True,blank=True)

    def __str__(self):
        return f"{self.member} - ₦{self.amount} ({self.status})"


    def approve(self, reviewed_by):
        """Approve withdrawal and deduct from member target savings"""

        if self.status != "pending":
            raise ValueError("Only pending withdrawals can be approved.")

        if self.amount > self.member.total_special_savings:
            raise ValueError("Withdrawal amount exceeds available target savings.")

        with transaction.atomic():

            self.status = "approved"
            self.reviewed_by = reviewed_by
            self.reviewed_at = timezone.now()
            self.save()

            member = self.member
            member.total_special_savings -= self.amount
            member.save(update_fields=["total_special_savings"])


    def reject(self, reviewed_by):
        """Reject withdrawal"""

        if self.status != "pending":
            raise ValueError("Only pending withdrawals can be rejected.")

        self.status = "rejected"
        self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now()
        self.save()