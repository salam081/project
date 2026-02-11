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
    user = models.ForeignKey(User, on_delete=models.CASCADE,blank=True, null=True)
    guest_name = models.CharField(max_length=255, blank=True, null=True)
    guest_phone = models.CharField(max_length=20, blank=True, null=True)
    guest_ippis = models.IntegerField(blank=True, null=True)
    consumable_type = models.ForeignKey(ConsumableType, on_delete=models.CASCADE, null=True, blank=True, related_name='consumables_type')
   
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')
    file_payslpt = models.ImageField(upload_to='file_payslpt', blank=True, null=True)
    passport = models.ImageField(upload_to='passports/', blank=True, null=True)

    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_consumables')
    date_created = models.DateTimeField(auto_now_add=True)
    
    
    def __str__(self):
        if self.user:
            return f"Request #{self.id} by {self.user.username}"
        return f"Request #{self.id} by Guest ({self.guest_name})"
    
    def calculate_total_price(self):
        return sum(detail.total_price for detail in self.details.all())
    
    @property
    def total_paid(self):
        return self.repayments.aggregate(total=Sum('amount_paid'))['total'] or 0
    
    @property
    def balance(self):
        return self.calculate_total_price() - self.total_paid
   
    def update_status_based_on_balance(self, save=True):
        """Automatically update status based on payment balance."""
        if self.balance <= 0 and self.status != 'FullyPaid':
            self.status = 'FullyPaid'
            if save:
                self.save(update_fields=['status'])

class ConsumableRequestDetail(models.Model):
    request = models.ForeignKey(ConsumableRequest, on_delete=models.CASCADE, related_name="details")
    selling_item = models.ForeignKey(SellingPlan, on_delete=models.CASCADE,related_name="details") 
    quantity = models.PositiveIntegerField(default=1)
    item_price = models.DecimalField(max_digits=10, decimal_places=2)
    loan_term_months = models.PositiveIntegerField()
    approved_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    approval_date = models.DateField(null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    

    def save(self, *args, **kwargs):
        # Only set item_price on first creation
        if not self.pk:
            self.item_price = self.selling_item.selling_price_per_unit
        super().save(*args, **kwargs)

    @property
    def total_price(self):
        return self.quantity * self.item_price
    
    @property
    def profit(self):
        purchased_item = self.selling_item.purchased_item
        cost_per_unit = purchased_item.unit_price + (purchased_item.expenditure_amount / purchased_item.quantity)
        return (self.item_price - cost_per_unit) * self.quantity
    
    def __str__(self):
        return f"{self.request} {self.quantity} x {self.selling_item.purchased_item.item_name} (Req #{self.request.id})"


class PaybackConsumable(models.Model):
    consumable_request = models.ForeignKey(ConsumableRequest, on_delete=models.CASCADE, related_name="repayments")
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    repayment_date = models.DateField()
    balance_remaining = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    payment_receipt = models.ImageField(upload_to='payment_receipts', blank=True, null=True)
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
    member = models.ForeignKey(Member,on_delete=models.CASCADE,related_name='consumable_fee', null=True, blank=True)
    consumable_type = models.ForeignKey(ConsumableType, on_delete=models.CASCADE)

    # Guest info (used if no member is attached)
    guest_name = models.CharField(max_length=255, null=True, blank=True)
    guest_ippis = models.CharField(max_length=20, null=True, blank=True)

    form_fee = models.DecimalField(max_digits=10, decimal_places=2)  
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="paid")
    created_by = models.ForeignKey(User,on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.member and self.member.member:
            user = self.member.member  # This is the related User instance
            return f"{user.first_name} {user.last_name} - ₦{self.form_fee}"
        else:
            return f"{self.guest_name or 'Guest'} ({self.guest_ippis or 'N/A'}) - ₦{self.form_fee}"


class PickedLog(models.Model):
    request_detail = models.ForeignKey( ConsumableRequestDetail, on_delete=models.CASCADE, related_name="picked_logs")
    picked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    picked_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.request_detail.selling_item.purchased_item.item_name} picked for Req#{self.request_detail.request.id}"
