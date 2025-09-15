from django.conf import settings
from django.db.models import Sum
from django.db import models
from accounts.models import *
from loan.models import BankName, BankCode
from django.utils import timezone

from PurchasedItems.models import SellingPlan


class Item(models.Model):
    title = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity_in_stock = models.PositiveIntegerField(default=0)
    description = models.TextField()
    available = models.BooleanField(default=True)

    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):

        if self.quantity_in_stock == 0 and self.available:
            self.available = False
        elif self.quantity_in_stock > 0 and not self.available:
            self.available = True
        super().save(*args, **kwargs)


class ConsumableType(models.Model):
    name = models.CharField(max_length=100) 
    description = models.TextField(blank=True, null=True) 
    request_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    available = models.BooleanField(default=True)
    created_by = models.ForeignKey(User,on_delete=models.CASCADE)
    
    
    def __str__(self):
        return self.name
    

class ConsumableRequest(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),('Approved', 'Approved'), ('Itempicked', 'Itempicked '),
        ('Declined', 'Declined'),('FullyPaid', 'FullyPaid'),]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    consumable_type = models.ForeignKey(ConsumableType, on_delete=models.CASCADE, null=True, blank=True, related_name='consumables_type')
   
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')
    file_payslpt = models.ImageField(upload_to='file_payslpt', blank=True, null=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_consumables')
    date_created = models.DateTimeField(auto_now_add=True)
    
    
    def __str__(self):
        return f"Request #{self.id} by {self.user.username}"
    
    def calculate_total_price(self):
        return sum(detail.total_price for detail in self.details.all())

    def total_paid(self):
        return self.repayments.aggregate(total=Sum('amount_paid'))['total'] or 0

    def balance(self):
        return self.calculate_total_price() - self.total_paid()

    def update_status_based_on_balance(self, save=True):
        """Automatically update status based on payment balance."""
        if self.balance() <= 0 and self.status != 'FullyPaid':
            self.status = 'FullyPaid'
            if save:
                self.save(update_fields=['status'])

class ConsumableRequestDetail(models.Model):
    request = models.ForeignKey(ConsumableRequest, on_delete=models.CASCADE, related_name="details")
    selling_item = models.ForeignKey(SellingPlan, on_delete=models.CASCADE) # 🔹 Change to SellingPlan
    quantity = models.PositiveIntegerField(default=1)
    item_price = models.DecimalField(max_digits=10, decimal_places=2)
    loan_term_months = models.PositiveIntegerField()
    approved_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    approval_date = models.DateField(null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)

    @property
    def total_price(self):
        return self.quantity * self.item_price
    
    def __str__(self):
        return f"{self.request} {self.quantity} x {self.selling_item.purchased_item.item_name} (Req #{self.request.id})"


class PaybackConsumable(models.Model):
    consumable_request = models.ForeignKey(ConsumableRequest, on_delete=models.CASCADE, related_name="repayments")
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    repayment_date = models.DateField()
    balance_remaining = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None

        if is_new:
            # Ensure all values are Decimal
            total_price = Decimal(self.consumable_request.calculate_total_price() or 0)
            total_paid_aggregate = self.consumable_request.repayments.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0.00')
            total_paid = Decimal(total_paid_aggregate) + Decimal(self.amount_paid)

            self.balance_remaining = total_price - total_paid

        super().save(*args, **kwargs)

        # Update request status if fully paid
        if is_new and self.balance_remaining <= 0:
            self.consumable_request.status = 'FullyPaid'
            self.consumable_request.save(update_fields=['status'])

    def __str__(self):
        return f"₦{self.amount_paid} for Req#{self.consumable_request.id} on {self.repayment_date}"


class ConsumableFormFee(models.Model):
    STATUS_CHOICES = [
        ("paid", "Paid"),             
        ("used", "Used for Loan"),     
        ("expired", "Expired/Closed"), # optional, if you want expiration
    ]
    member = models.ForeignKey(Member,on_delete=models.CASCADE,related_name='consumable_fee')
    consumable_type = models.ForeignKey(ConsumableType, on_delete=models.CASCADE)
    form_fee = models.DecimalField(max_digits=10, decimal_places=2)  
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="paid")
    created_by = models.ForeignKey(User,on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.member.member.first_name} {self.member.member.last_name} - ₦{self.form_fee}"


