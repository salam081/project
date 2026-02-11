from django.db import models
from accounts.models import *
# Create your models here.


class Savings(models.Model):
    member = models.ForeignKey("accounts.Member", on_delete=models.CASCADE,related_name="savings")
    month = models.DateField(db_index=True)
    month_saving = models.DecimalField(max_digits=10, decimal_places=2)
    original_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ("member", "month")  # Prevents duplicates for the same month
        indexes = [
        models.Index(fields=["member", "month"]),
    ]
        
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.member.update_total_savings()


    def __str__(self):
        return f"{self.member} - {self.month.strftime('%B %Y')}: ₦{self.month_saving}"

    
    

class Interest(models.Model):
    member = models.ForeignKey("accounts.Member", on_delete=models.CASCADE)
    month = models.DateField(db_index=True)  
    amount_deducted = models.DecimalField(max_digits=10, decimal_places=2, default=400.00)
    date_deducted = models.DateField(auto_now_add=True)
    class Meta:
        unique_together = ("member", "month")  # Prevent duplicate deductions

    def __str__(self):
        return f"{self.member} - {self.amount_deducted} for {self.month.strftime('%B %Y')}"


class Loanable(models.Model):
    member = models.ForeignKey("accounts.Member", on_delete=models.CASCADE)
    month = models.DateField(db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, null=False, blank=False)
    date_created = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.member} - {self.amount} -  {self.month.strftime('%B %Y')}"

class Investment(models.Model):
    member = models.ForeignKey("accounts.Member", on_delete=models.CASCADE)
    month = models.DateField(db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    date_created = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"{self.member} - {self.amount} - {self.month.strftime('%B %Y')}"


class InterestAmount(models.Model):
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey("accounts.User", on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.amount}"
    
class DeleteLog(models.Model):
    ACTION_CHOICES = [('monthly_savings_delete', 'Monthly Savings Delete'),]

    user = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=100, choices=ACTION_CHOICES)
    month = models.DateField()
    records_deleted = models.PositiveIntegerField(default=0)
    timestamp = models.DateTimeField(auto_now_add=True)
    remarks = models.TextField(blank=True, null=True)

    def __str__(self):
        user_name = f"{self.user.first_name} {self.user.last_name}" if self.user else "Unknown User"
        return f"{user_name} deleted {self.records_deleted} records for {self.month.strftime('%B %Y')}"
