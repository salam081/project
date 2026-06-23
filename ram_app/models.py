from django.db import models
from django.db.models import Sum
from decimal import Decimal
from accounts.models import *




class Budget(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    name = models.CharField(max_length=255)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    is_active = models.BooleanField(default=True)
    date_created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="budgets")
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_budgets")
    approved_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date_created"]

    def __str__(self):
        return self.name

    @property
    def total_spent(self):
        # Sum cost_price of all approved request items under this budget
        result = RamRequestDetails.objects.filter(
            request__budget=self,
            request__status="approved"
        ).aggregate(
            total=Sum(models.F("cost_price") * models.F("quantity"))
        )
        return result["total"] or Decimal("0.00")
       

    @property
    def remaining_amount(self):
        return self.total_amount - self.total_spent

class Markup(models.Model):
    name = models.CharField(max_length=255)       # e.g. "Standard Plan"
    percentage = models.DecimalField(max_digits=5, decimal_places=2)  # e.g. 20.00
    is_active = models.BooleanField(default=False)
    date_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.percentage}%)"

class RamRequest(models.Model):
    STATUS_CHOICES = [("pending", "Pending"),("approved", "Approved"),('fully Paid', 'Fully Paid'), ("rejected", "Rejected"),]

    budget = models.ForeignKey(Budget, on_delete=models.PROTECT, related_name="requests")
    member = models.ForeignKey(Member, on_delete=models.SET_NULL, null=True, related_name="budget_requests")
    guest_name = models.CharField(max_length=255, blank=True, null=True)
    guest_phone = models.CharField(max_length=20, blank=True, null=True)
    guest_ippis = models.IntegerField(blank=True, null=True)
    file_payslip = models.ImageField(upload_to='request_payslips/', blank=True, null=True)
    guarantor = models.ForeignKey(Member, on_delete=models.SET_NULL, null=True, blank=True, related_name="ram_guaranteed")
    guarantor_accepted = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    date_requested = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_requests")
    approved_date = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="created_requests")
    note = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-date_requested"]

    def __str__(self):
        return f"Request by {self.member} on {self.date_requested.date()}"

    @property
    def total_cost_price(self):
        result = self.items.aggregate(total=Sum("cost_price"))
        return result["total"] or Decimal("0.00")

    @property
    def total_selling_price(self):
        result = self.items.aggregate(total=Sum("selling_price"))
        return result["total"] or Decimal("0.00")

    @property
    def total_paid(self):
        result = self.payments.aggregate(total=Sum("amount"))
        return result["total"] or Decimal("0.00")

    @property
    def balance_remaining(self):
        return self.total_selling_price - self.total_paid

    @property
    def is_fully_paid(self):
        return self.balance_remaining <= Decimal("0.00")


class RamRequestDetails(models.Model):
    request = models.ForeignKey(RamRequest, on_delete=models.CASCADE, related_name="items")
    item_name = models.CharField(max_length=255)   
    quantity = models.PositiveIntegerField(default=1)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2)    # what cooperative pays per item
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, editable=False)  # cost + 20%
    duration_months = models.PositiveIntegerField()
    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f" {self.item_name} {self.quantity}x for {self.request}"
    
    def save(self, *args, **kwargs):
        cost = Decimal(str(self.cost_price))
        plan = Markup.objects.filter(is_active=True).first()
        if plan:
            markup = plan.percentage / Decimal("100")
            self.selling_price = (cost * (1 + markup)).quantize(Decimal("0.01"))
        else:
            self.selling_price = cost  # fallback: no markup
        super().save(*args, **kwargs)
        
 
    @property
    def total_cost_price(self):
        return self.cost_price * self.quantity

    @property
    def total_selling_price(self):
        return self.selling_price * self.quantity


class Payment(models.Model):
    request = models.ForeignKey(RamRequest, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    repayment_mounth = models.DateField()
    payment_receipt = models.ImageField(upload_to='payment_receipts', blank=True, null=True)
    date_paid = models.DateTimeField(auto_now_add=True)
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="received_payments")
    note = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-date_paid"]

    def __str__(self):
        return f"Payment of {self.amount} for {self.request}"