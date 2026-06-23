# models.py
from django.db import models
from accounts.models import *
from decimal import Decimal
from django.db import models
from django.db.models import Sum
from django.core.exceptions import ValidationError
from django.db.models import Sum, F, DecimalField
from django.db.models.functions import Coalesce
from django.db.models import F, Sum, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce





class Supplier(models.Model):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=255, blank=True)
    address = models.TextField(blank=True)

    def __str__(self):
        return self.name


class StockIn(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    note = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    received_by = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"StockIn #{self.pk} from {self.supplier.name}"

    @property
    def get_total_cost(self):
        return sum(item.total_price for item in self.items.all())

    @property
    def net_voucher_value(self):
        total_received = self.get_total_cost
        total_returned = sum(
            ret.quantity * item.unit_price
            for item in self.items.all()
            for ret in item.stockreturn_set.all()
        )
        return total_received - total_returned


class ReceivedItem(models.Model):
    stock_in = models.ForeignKey(StockIn, related_name='items', on_delete=models.CASCADE)
    brand = models.CharField(max_length=100)
    model_name = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    received_by = models.ForeignKey(User, on_delete=models.CASCADE)
    brand_image = models.ImageField(upload_to='brand_images/', blank=True, null=True)
    received_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"{self.brand} {self.model_name} (x{self.quantity})"

    @property
    def total_price(self):
        return self.quantity * self.unit_price

    @property
    def net_quantity(self):
        returns = sum(ret.quantity for ret in self.stockreturn_set.all())
        return self.quantity - returns

    @property
    def net_stock_value(self):
        return self.net_quantity * self.unit_price


class StockReturn(models.Model):
    stock_item = models.ForeignKey(ReceivedItem, on_delete=models.CASCADE)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    reason = models.TextField(help_text="Reason for return (e.g. damaged, overstock)")
    returned_at = models.DateTimeField(auto_now_add=True)
    returned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"Return: {self.stock_item.model_name} ({self.quantity})"

    def clean(self):
        if self.quantity > self.stock_item.net_quantity:
            raise ValidationError(
                f"Cannot return {self.quantity}. "
                f"Only {self.stock_item.net_quantity} units available."
            )


class SellingPlan(models.Model):
    received_item = models.OneToOneField(ReceivedItem, on_delete=models.CASCADE, related_name='selling_plan')
    selling_price_per_unit = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField()
    notes = models.TextField(blank=True, null=True)
    profit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    available = models.BooleanField(default=True)
    include_expenditure = models.BooleanField(default=True)
    date_created = models.DateField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="inventory_selling_plans")

    class Meta:
        ordering = ['-date_created']

    def clean(self):
        if not self.selling_price_per_unit or self.selling_price_per_unit <= 0:
            raise ValidationError(
                {'selling_price_per_unit': 'Selling price must be greater than zero'}
            )
        if not self.quantity or self.quantity <= 0:
            raise ValidationError({'quantity': 'Quantity must be greater than zero'})

        # FIX: use net_quantity (accounts for returns) instead of raw quantity
        available = self.received_item.net_quantity
        if self.quantity > available:
            raise ValidationError({
                'quantity': f'Cannot plan to sell {self.quantity}. Only {available} units available after returns.'
            })

    @property
    def total_sale_value(self):
        return (self.selling_price_per_unit or Decimal('0.00')) * self.quantity

    @property
    def purchase_cost(self):
        # FIX: removed duplicate `or self.received_item.unit_price`
        base = self.received_item.unit_price or Decimal('0.00')
        return base * self.quantity

    def update_profit(self, save=True):
        self.profit = self.total_sale_value - self.purchase_cost
        if save:
            self.save(update_fields=["profit"])
        return self.profit

    def __str__(self):
        return (
            f"{self.received_item.brand} {self.received_item.model_name} "
            f"| ₦{self.selling_price_per_unit} | Qty: {self.quantity}"
        )


# ──────────────────────────────────────────────
#  MEMBER REQUEST MODELS
# ──────────────────────────────────────────────

class MemberRequest(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Declined', 'Declined'),
        ('ItemPicked', 'ItemPicked'),
        ('Fully Paid', 'Fully Paid'),
    ]

    member = models.ForeignKey(Member, on_delete=models.CASCADE, null=True, blank=True, related_name='member_requests')
    guest_name = models.CharField(max_length=255, blank=True, null=True)
    guest_phone = models.CharField(max_length=20, blank=True, null=True)
    guest_ippis = models.IntegerField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    file_payslip = models.ImageField(upload_to='request_payslips/', blank=True, null=True)
    passport_photo = models.ImageField(upload_to='request_passports/', blank=True, null=True)
    guarantor = models.ForeignKey(Member, on_delete=models.SET_NULL, null=True, blank=True, related_name="guaranteed")
    guarantor_accepted = models.BooleanField(default=False)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,related_name='approved_member_requests')
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_created']

    def __str__(self):
        return f"Request #{self.id} - {self.member or self.guest_name}"

    def clean(self):
        if not self.member and not self.guest_name:
            raise ValidationError("Provide a user or guest details.")

    def save(self, *args, **kwargs):
        # FIX: only run full_clean on full saves, not partial update_fields saves
        if not kwargs.get('update_fields'):
            self.full_clean()
        super().save(*args, **kwargs)

    def calculate_total_price(self):
        total = Decimal('0.00')
        for d in self.details.all():
            total += d.total_price  # uses total_price property which respects markup
        return total

    @property
    def total_paid(self):
        return self.repayments.aggregate(
            total=Coalesce(Sum('amount_paid'), Decimal('0.00'))
        )['total']

    @property
    def balance(self):
        total = self.calculate_total_price() or Decimal('0.00')
        paid = self.total_paid or Decimal('0.00')
        return total - paid

    def update_status_based_on_balance(self):
        total = self.calculate_total_price() or Decimal('0.00')
        paid = self.total_paid or Decimal('0.00')
        if total - paid <= Decimal('0.00'):
            self.status = 'Fully Paid'
            self.save(update_fields=['status'])

class MemberRequestDetail(models.Model):
    request = models.ForeignKey(MemberRequest, on_delete=models.CASCADE, related_name='details')
    item = models.ForeignKey(SellingPlan, on_delete=models.PROTECT, related_name='request_details')
    quantity = models.PositiveIntegerField(default=0)
    item_price = models.DecimalField(max_digits=12, decimal_places=2)
    markup_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,help_text="Markup rate as a percentage (e.g., 5.00 for 5%).")
    approved_quantity = models.PositiveIntegerField(null=True, blank=True)
    duration_months = models.PositiveIntegerField()
    approval_date = models.DateField(null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if is_new:
            self.item_price = self.item.selling_price_per_unit

            # apply markup to item_price if provided
            if self.markup_rate:
                markup_multiplier = 1 + (self.markup_rate / Decimal('100'))
                self.item_price = (self.item_price * markup_multiplier).quantize(Decimal('0.01'))

            qty = self.approved_quantity or self.quantity
            if qty <= 0:
                raise ValidationError("Quantity must be greater than zero.")
            if self.item.quantity < qty:
                raise ValidationError(
                    f"Not enough stock in selling plan. Available: {self.item.quantity}"
                )
            self.item.quantity -= qty
            self.item.save(update_fields=['quantity'])

        super().save(*args, **kwargs)

    @property
    def marked_up_price(self):
        """Item price after markup — useful for display."""
        if self.markup_rate:
            return (self.item_price * (1 + self.markup_rate / Decimal('100'))).quantize(Decimal('0.01'))
        return self.item_price

    @property
    def total_price(self):
        qty = self.approved_quantity if self.approved_quantity else self.quantity
        return qty * self.item_price  # item_price already includes markup if applied at save

    def __str__(self):
        return f"{self.quantity} x {self.item.received_item.brand} ({self.request.id})"



class MemberRequestPayback(models.Model):
    member_request = models.ForeignKey(MemberRequest, on_delete=models.CASCADE, related_name='repayments')
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    repayment_date = models.DateField()
    balance_remaining = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    payment_receipt = models.ImageField(upload_to='member_request_receipts/', blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recorded_request_payments')
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.amount_paid <= 0:
            raise ValidationError("Amount must be greater than zero.")

        total_price = self.member_request.calculate_total_price() or Decimal('0.00')

        prior_paid = self.member_request.repayments.exclude(pk=self.pk).aggregate(
            total=Coalesce(Sum('amount_paid'), Decimal('0.00'))
        )['total']

        remaining = total_price - prior_paid

        if self.amount_paid > remaining:
            raise ValidationError(
                f"Payment of ₦{self.amount_paid} exceeds remaining balance of ₦{remaining}."
            )

    def save(self, *args, **kwargs):
        # Skip full_clean on partial update_fields saves
        if not kwargs.get('update_fields'):
            self.full_clean()

        total_price = self.member_request.calculate_total_price() or Decimal('0.00')

        # Exclude self so we don't read stale DB state before this record is written
        prior_paid = self.member_request.repayments.exclude(pk=self.pk).aggregate(
            total=Coalesce(Sum('amount_paid'), Decimal('0.00'))
        )['total']

        # Include current payment manually — DB doesn't have it yet
        self.balance_remaining = max(
            total_price - prior_paid - self.amount_paid,
            Decimal('0.00')
        )

        super().save(*args, **kwargs)

        self.member_request.update_status_based_on_balance()

    def __str__(self):
        return f"₦{self.amount_paid} - Req#{self.member_request.id}"