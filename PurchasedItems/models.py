from django.db import models
from accounts.models import *
from consumable.models import *
from main.models import *
from member.models import *

# Create your models here.
from decimal import Decimal
from django.db import models
from accounts.models import User
from django.db import models

from django.db.models import Sum, F, DecimalField
from django.db.models.functions import Coalesce
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone



class ConsumablePurchasedRequest(models.Model):
    """Model for tracking consumable purchase requests"""
    STATUS_PENDING = 'pending'
    STATUS_REVIEWED = 'reviewed'
    STATUS_APPROVED = 'approved'
    STATUS_ACCOUNTED = 'accounted'
    
    STATUS_CHOICES = [(STATUS_PENDING, 'Pending'),(STATUS_REVIEWED, 'Reviewed'),(STATUS_APPROVED, 'Approved'),(STATUS_ACCOUNTED, 'Fully Accounted'),]

    requested_by = models.ForeignKey( User, on_delete=models.CASCADE,related_name='consumable_requests')
    item = models.CharField(max_length=255)
    purpose = models.CharField(max_length=255)
    amount_requested = models.DecimalField( max_digits=12,  decimal_places=2, help_text="Amount requested for purchase")
    approved_amount = models.DecimalField(max_digits=12,  decimal_places=2, null=True, blank=True,help_text="Amount approved by admin")
    status = models.CharField( max_length=20, choices=STATUS_CHOICES,  default=STATUS_PENDING)
    approved_by = models.ForeignKey( User, on_delete=models.SET_NULL, null=True, blank=True, related_name='consumable_approvals')
    date_requested = models.DateField(auto_now_add=True)
    date_approved = models.DateField(null=True, blank=True)
    remarks = models.TextField(blank=True, null=True)
    comment = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-date_requested']
        verbose_name = "Consumable Purchase Request"
        verbose_name_plural = "Consumable Purchase Requests"
    
    def review(self, reviewed_by, comment=None):
        """Mark request as reviewed before approval"""
        if self.status != self.STATUS_PENDING:
            raise ValidationError("Only pending requests can be reviewed.")
        
        self.status = self.STATUS_REVIEWED
        self.approved_by = reviewed_by
        self.comment = comment or ""
        self.date_approved = timezone.now().date()
        self.save()
        
    def clean(self):
        """Validate model data"""
        if self.amount_requested and self.amount_requested <= 0:
            raise ValidationError({'amount_requested': 'Amount must be greater than zero'})
        
        if self.approved_amount and self.approved_amount <= 0:
            raise ValidationError({'approved_amount': 'Approved amount must be greater than zero'})
        
        if self.status == self.STATUS_APPROVED and not self.approved_amount:
            raise ValidationError({'approved_amount': 'Approved amount is required for approved requests'})

   
    def total_spent(self):
        """Calculate total amount spent on purchased items including expenditure"""
        return self.items.aggregate(
            total=Coalesce(
                Sum(
                    F('quantity') * F('unit_price') + F('expenditure_amount'), 
                    output_field=DecimalField()
                ),
                Decimal('0')
            )
        )['total']

   
    def balance_remaining(self):
        """Calculate remaining balance"""
        if not self.approved_amount:
            return None
        return self.approved_amount - self.total_spent()

    def is_fully_accounted(self):
        """Check if request is fully accounted"""
        return self.status == self.STATUS_ACCOUNTED

    def can_add_item(self, item_total):
        """Check if an item with given total can be added"""
        if self.status != self.STATUS_APPROVED:
            return False, "Request must be approved to add items"
        
        balance = self.balance_remaining()
        if balance is None:
            return False, "No approved amount set"
        
        if item_total > balance:
            return False, f"Insufficient balance. Available: ₦{balance:.2f}, Required: ₦{item_total:.2f}"
        
        return True, "OK"

    def can_be_modified(self):
        """Check if request can be modified"""
        return self.status == self.STATUS_PENDING
    
    def approve(self, approved_amount, approved_by):
        """Approve the request after review"""
        if self.status != self.STATUS_REVIEWED:
            raise ValidationError("Only reviewed requests can be approved.")
        
        if approved_amount <= 0:
            raise ValidationError("Approved amount must be greater than zero.")
        
        self.approved_amount = approved_amount
        self.approved_by = approved_by
        self.status = self.STATUS_APPROVED
        self.date_approved = timezone.now().date()
        self.save()

    def mark_as_accounted(self):
        """Mark request as fully accounted"""
        if self.status != self.STATUS_APPROVED:
            raise ValidationError("Only approved requests can be marked as accounted")
        
        total_spent = self.total_spent()
        self.approved_amount = total_spent
        self.status = self.STATUS_ACCOUNTED
        self.remarks = (self.remarks or '') + f"\n\nAccounted on {timezone.now().date()}"
        self.save()
    
    def __str__(self):
        return f"{self.requested_by} | ₦{self.amount_requested} | {self.get_status_display()}"


class PurchasedItem(models.Model):
    """Model for items purchased under a consumable request"""
    consumable_purchased_request = models.ForeignKey( ConsumablePurchasedRequest, on_delete=models.CASCADE, related_name='items')
    item_name = models.CharField(max_length=255)
    description = models.TextField(help_text="Item description")
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, help_text="Price per unit")
    receipt = models.FileField(upload_to='receipts/%Y/%m/', blank=True, null=True, help_text="Upload receipt image")
    expenditure_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'),help_text="Additional expenditure (transport, etc.)")
    date_added = models.DateField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

   
    class Meta:
        ordering = ['-date_added']
        verbose_name = "Purchased Item"
        verbose_name_plural = "Purchased Items"

    def clean(self):
        """Validate model data"""
        if self.quantity <= 0:
            raise ValidationError({'quantity': 'Quantity must be greater than zero'})
        
        if self.unit_price <= 0:
            raise ValidationError({'unit_price': 'Unit price must be greater than zero'})
        
        if self.expenditure_amount < 0:
            raise ValidationError({'expenditure_amount': 'Expenditure amount cannot be negative'})

    @property
    def cost_per_unit(self):
        """Cost per unit including proportional expenditure allocation"""
        if self.quantity > 0:
            total_cost = (self.unit_price * self.quantity) + (self.expenditure_amount or Decimal('0.00'))
            return total_cost / self.quantity
        return self.unit_price

    @property
    def total_price(self):
        """Total purchase price including expenditure"""
        return (self.unit_price * self.quantity) + (self.expenditure_amount or Decimal('0'))

    def __str__(self):
        return f"{self.item_name} | ₦{self.unit_price} | Qty: {self.quantity}"


class SellingPlan(models.Model):
    """Model for planning the sale of purchased items"""
    purchased_item = models.OneToOneField(PurchasedItem, on_delete=models.CASCADE, related_name='selling_plan')
    selling_price_per_unit = models.DecimalField(max_digits=12, decimal_places=2,help_text="Selling price per unit")
    quantity = models.PositiveIntegerField(help_text="Quantity to sell")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    date_created = models.DateField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)
    profit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,help_text="Calculated profit")
    available = models.BooleanField(default=True)
    include_expenditure = models.BooleanField(default=True,help_text="Include purchased item expenditure in cost calculation")
   
    class Meta:
        ordering = ['-date_created']
        verbose_name = "Selling Plan"
        verbose_name_plural = "Selling Plans"

    def clean(self):
        """Validate model data"""
        if self.selling_price_per_unit <= 0:
            raise ValidationError({'selling_price_per_unit': 'Selling price must be greater than zero'})
        
        if self.quantity <= 0:
            raise ValidationError({'quantity': 'Quantity must be greater than zero'})
        
        if self.quantity > self.purchased_item.quantity:
            raise ValidationError({
                'quantity': f'Cannot sell {self.quantity} units. Only {self.purchased_item.quantity} available.'
            })

    @property
    def total_sale_value(self):
        """Total revenue from sales"""
        return (self.selling_price_per_unit or Decimal('0.00')) * self.quantity

    @property
    def purchase_cost(self):
        """Purchase cost based on include_expenditure flag"""
        if self.include_expenditure:
            return (self.purchased_item.cost_per_unit or Decimal('0.00')) * self.quantity
        return (self.purchased_item.unit_price or Decimal('0.00')) * self.quantity

    @property
    def total_profit(self):
        """Total profit calculation"""
        return self.profit if self.profit is not None else (self.total_sale_value - self.purchase_cost)

    def update_profit(self, save=True):
        """Update profit calculation"""
        self.profit = self.total_sale_value - self.purchase_cost
        if save:
            self.save(update_fields=["profit"])
        return self.profit

    def __str__(self):
        return f"{self.purchased_item.item_name} | ₦{self.selling_price_per_unit} | Qty: {self.quantity}"



class PurchasedItemAdjustment(models.Model):
    """Track price adjustments for purchased items"""
    purchased_item = models.ForeignKey(PurchasedItem, on_delete=models.CASCADE, related_name="adjustments")
    old_price = models.DecimalField(max_digits=12, decimal_places=2)
    new_price = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField(blank=True, null=True)
    adjusted_by = models.ForeignKey(User,on_delete=models.SET_NULL,null=True)
    date_adjusted = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_adjusted']
        verbose_name = "Purchased Item Adjustment"
        verbose_name_plural = "Purchased Item Adjustments"

    def clean(self):
        """Validate adjustment data"""
        if self.new_price <= 0:
            raise ValidationError({'new_price': 'New price must be greater than zero'})

    def __str__(self):
        return f"Adjustment for {self.purchased_item.item_name} on {self.date_adjusted:%Y-%m-%d}"


class SellingPlanAdjustment(models.Model):
    """Track price adjustments for selling plans"""
    selling_plan = models.ForeignKey(SellingPlan,  on_delete=models.CASCADE, related_name="adjustments" )
    old_price = models.DecimalField(max_digits=12, decimal_places=2)
    new_price = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField(blank=True, null=True)
    adjusted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    date_adjusted = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_adjusted']
        verbose_name = "Selling Plan Adjustment"
        verbose_name_plural = "Selling Plan Adjustments"

    def clean(self):
        """Validate adjustment data"""
        if self.new_price <= 0:
            raise ValidationError({'new_price': 'New price must be greater than zero'})

    def __str__(self):
        return f"Adjustment for {self.selling_plan.purchased_item.item_name} on {self.date_adjusted:%Y-%m-%d}"