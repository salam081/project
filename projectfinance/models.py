from django.db import models
from accounts.models import *
# models.py
class ProjectFinanceApplication(models.Model):
    STATUS_CHOICES = [('Pending', 'Pending'),('Reviewed', 'Reviewed'),('Rejected', 'Rejected')]
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="project_finance_applications")
    application_letter = models.TextField()
    comments = models.TextField(blank=True,null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')  # <-- NEW FIELD

    def __str__(self):
        return f"Application by {self.member.member.first_name} {self.member.member.last_name} - {self.created_at.strftime('%Y-%m-%d')}"

class ProjectFinanceRequest(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Declined', 'Declined'),
        ('Completed', 'Completed'),
        ('FullyPaid', 'Fully Paid'),
    ]
    GUARANTOR_STATUS = [('Pending', 'Pending'), ('Approved', 'Approved'), ('Declined', 'Declined')]
    
    application = models.ForeignKey(ProjectFinanceApplication, on_delete=models.CASCADE, related_name="requests")
    product = models.CharField(max_length=255)
    requested_amount = models.DecimalField(max_digits=12, decimal_places=2, help_text="The amount requested by the member.")
    markup_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Markup rate as a percentage (e.g., 5.00 for 5%).")

    total_repayment_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="The total amount to be repaid, including markup.")
    
    guarantor = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="guaranteed_project_finances")
    guarantor_status = models.CharField(max_length=20, choices=GUARANTOR_STATUS, default='Pending')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    balance_remaining = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_project_finances')

    def save(self, *args, **kwargs):
        # Calculate the total repayment amount and initial balance
        # only if a markup_rate is provided and is not None.
        if self.markup_rate is not None:
            # The Decimal() conversion is crucial for safety and precision.
            markup_amount = (self.requested_amount * self.markup_rate) / Decimal('100')
            self.total_repayment_amount = self.requested_amount + markup_amount
            
            # Initialize balance_remaining only on initial save
            if self.balance_remaining is None:
                self.balance_remaining = self.total_repayment_amount
                
        # If markup_rate is not provided (e.g., on initial application save), set repayment to requested_amount
        else:
            self.total_repayment_amount = self.requested_amount
            if self.balance_remaining is None:
                self.balance_remaining = self.requested_amount

        super().save(*args, **kwargs)

    def update_balance_remaining(self):
        # The logic is fine, but it should be called as needed.
        # It's better to keep this as a separate method for clarity.
        if self.total_repayment_amount is not None:
            total_paid = self.payments.aggregate(total=models.Sum('amount_paid'))['total'] or Decimal('0.00')
            self.balance_remaining = self.total_repayment_amount - total_paid

            if self.balance_remaining <= 0:
                self.balance_remaining = Decimal('0.00')
                self.status = 'FullyPaid'
            
            self.save()

    def __str__(self):
        return f"{self.application.member.member.first_name} - {self.product}"

from django.db import models
from django.db.models import Sum
from django.conf import settings

class ProjectFinancePayment(models.Model):
    request = models.ForeignKey(ProjectFinanceRequest, on_delete=models.CASCADE, related_name="payments")
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    month = models.DateField(help_text="Select the month for this payment")
    balance_remaining = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL, null=True,blank=True, related_name='project_finance_payments_recorded')

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        if is_new:
            total_price = self.request.total_repayment_amount or self.request.requested_amount
            total_paid = (
                self.request.payments.aggregate(total=Sum('amount_paid'))['total'] or 0
            ) + self.amount_paid

            self.balance_remaining = total_price - total_paid

        super().save(*args, **kwargs)

        # Update request balance and status
        if is_new:
            self.request.update_balance_remaining()

    def __str__(self):
        return f"₦{self.amount_paid} for Req#{self.request.id} on {self.month.strftime('%B %Y')}"
