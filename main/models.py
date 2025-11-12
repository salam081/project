from django.db import models
from django.conf import settings
from decimal import Decimal
from django.db import models, transaction
from django.utils import timezone
from decimal import Decimal
from django.contrib.auth import get_user_model
from accounts.models import *
from savings.models import *
from loan.models import *
from consumable.models import *

User = get_user_model()

class FinancialSummary(models.Model):
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name="financial_summaries")
    total_savings = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_interest = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_loanable = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_investment = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    # grand_total = models.DecimalField(max_digits=15, decimal_places=2)
    grand_total = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        timestamp = self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        if self.user:
            return f"Summary for {self.user.username} at {timestamp} - Grand Total: {self.grand_total}"
        return f"Summary at {timestamp} (No User) - Grand Total: {self.grand_total}"
    

    @classmethod
    def recalculate_grand_total(cls):
        return cls.objects.aggregate(total=models.Sum('grand_total'))['total'] or Decimal('0.00')

    class Meta:
        verbose_name = "Financial Summary"
        verbose_name_plural = "Financial Summaries"
        ordering = ['-created_at']


class Withdrawal(models.Model):
    STATUS_CHOICES = [ ('Pending', 'Pending'),('Approved', 'Approved'), ('Declined', 'Declined'),]
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='withdrawal_requests')
    reason = models.TextField(blank=True, null=True)
    date_requested = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_withdrawals')
    date_approved = models.DateTimeField(null=True, blank=True)

    # Track the amounts at the time of withdrawal for record keeping
    withdrawn_savings = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    withdrawn_loanable = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    withdrawn_investment = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total_withdrawn = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.member} - {self.status}"
    
   
    def approve(self, admin_user):
        """Approve the withdrawal request and process the funds"""
        with transaction.atomic():
            # Get total savings
            total_savings = Savings.objects.filter(member=self.member).aggregate(
                total=models.Sum('month_saving')
            )['total'] or Decimal('0.00')

            # Get available loanable and investment
            total_loanable = Loanable.objects.filter(member=self.member).aggregate(
                total=models.Sum('amount')
            )['total'] or Decimal('0.00')

            total_investment = Investment.objects.filter(member=self.member).aggregate(
                total=models.Sum('amount')
            )['total'] or Decimal('0.00')

            # Calculate how much to remove from each (match withdrawn_savings)
            loanable_to_withdraw = min(total_savings, total_loanable)
            investment_to_withdraw = min(total_savings, total_investment)

            # Track what was withdrawn
            self.withdrawn_savings = total_savings
            self.withdrawn_loanable = loanable_to_withdraw
            self.withdrawn_investment = investment_to_withdraw
            self.total_withdrawn = total_savings  # Only savings is paid out

            self.status = "Approved"
            self.date_approved = timezone.now()
            self.approved_by = admin_user
            self.save()

            # Delete savings records and update member total
            Savings.objects.filter(member=self.member).delete()
            self.member.total_savings = Decimal('0.00')
            self.member.save()

            # Reduce loanable and investment accordingly
            Loanable.objects.filter(member=self.member).delete()
            Investment.objects.filter(member=self.member).delete()


    def decline(self, admin_user, reason=None):
        
        with transaction.atomic():
            self.status = "Declined"
            self.date_approved = timezone.now()
            self.approved_by = admin_user
            self.save()


    def get_member_financial_summary(self):
        """Get complete financial summary for the member"""
        from .models import Savings, Interest, Loanable, Investment

        total_savings = Savings.objects.filter(member=self.member).aggregate(
            total=models.Sum('month_saving')
        )['total'] or Decimal('0.00')

        total_interest = Interest.objects.filter(member=self.member).aggregate(
            total=models.Sum('amount_deducted')
        )['total'] or Decimal('0.00')

        total_loanable = Loanable.objects.filter(member=self.member).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')

        total_investment = Investment.objects.filter(member=self.member).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')

        return {
            'total_savings': total_savings,
            'total_interest': total_interest,
            'total_loanable': total_loanable,
            'total_investment': total_investment,
            'grand_total': total_savings  # ONLY savings considered withdrawn
        }


class PartialWithdrawal(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Declined', 'Declined'),
    ]
    
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='partial_withdrawals')
    amount_requested = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField(blank=True, null=True)
    date_requested = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    
    # Admin fields
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    date_approved = models.DateTimeField(null=True, blank=True)
    decline_reason = models.TextField(blank=True, null=True)
    
    # Record keeping
    withdrawn_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    withdrawn_from_loanable = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    withdrawn_from_investment = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.member} - ₦{self.amount_requested} - {self.status}"

    @transaction.atomic
    def approve(self, admin_user):
        """Approve and process withdrawal"""
        # Get totals
        total_savings = Savings.objects.filter(member=self.member).aggregate(
            total=models.Sum('month_saving')
        )['total'] or Decimal('0.00')
        
        total_loanable = Loanable.objects.filter(member=self.member).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
        
        total_investment = Investment.objects.filter(member=self.member).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
        
        # Check if enough money
        if self.amount_requested > total_savings:
            raise ValueError(f"Not enough savings. Available: ₦{total_savings:,.2f}")
        
        # Calculate 50/50 split
        from_loanable = self.amount_requested / Decimal('2.00')
        from_investment = self.amount_requested / Decimal('2.00')
        
        if from_loanable > total_loanable:
            raise ValueError("Not enough in loanable account")
        
        if from_investment > total_investment:
            raise ValueError("Not enough in investment account")
        
        # Save withdrawal info
        self.withdrawn_amount = self.amount_requested
        self.withdrawn_from_loanable = from_loanable
        self.withdrawn_from_investment = from_investment
        self.status = "Approved"
        self.date_approved = timezone.now()
        self.approved_by = admin_user
        self.save()
        
        # Update member total
        self.member.total_savings = total_savings - self.amount_requested
        self.member.save()
        
        # Reduce savings
        self._reduce_savings(self.amount_requested)
        self._reduce_loanable(from_loanable)
        self._reduce_investment(from_investment)
    
    def _reduce_savings(self, amount):
        """Remove from savings records"""
        remaining = amount
        savings_list = Savings.objects.filter(member=self.member).order_by('date_created')
        
        for saving in savings_list:
            if remaining <= 0:
                break
            if saving.month_saving <= remaining:
                remaining -= saving.month_saving
                saving.delete()
            else:
                saving.month_saving -= remaining
                saving.save()
                remaining = Decimal('0.00')
    
    def _reduce_loanable(self, amount):
        """Remove from loanable records"""
        remaining = amount
        loanable_list = Loanable.objects.filter(member=self.member).order_by('date_created')
        
        for loanable in loanable_list:
            if remaining <= 0:
                break
            if loanable.amount <= remaining:
                remaining -= loanable.amount
                loanable.delete()
            else:
                loanable.amount -= remaining
                loanable.save()
                remaining = Decimal('0.00')
    
    def _reduce_investment(self, amount):
        """Remove from investment records"""
        remaining = amount
        investment_list = Investment.objects.filter(member=self.member).order_by('date_created')
        
        for investment in investment_list:
            if remaining <= 0:
                break
            if investment.amount <= remaining:
                remaining -= investment.amount
                investment.delete()
            else:
                investment.amount -= remaining
                investment.save()
                remaining = Decimal('0.00')
    
    def decline(self, admin_user, reason):
        """Decline withdrawal"""
        self.status = "Declined"
        self.date_approved = timezone.now()
        self.approved_by = admin_user
        self.decline_reason = reason
        self.save()

    class Meta:
        ordering = ['-date_requested']


class Dividend(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="member_dividends")
    profit = models.DecimalField(max_digits=15, decimal_places=2)  # The profit entered by admin
    unit_profit = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)  # Profit per share
    dividend_amount = models.DecimalField(max_digits=15, decimal_places=2)  # What this member got
    date = models.DateField(blank=True,null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User,on_delete=models.SET_NULL, null=True,blank=True,related_name="created_dividends")

    def __str__(self):
        return f"Dividend {self.dividend_amount} (Unit Profit: {self.unit_profit}) for {self.member} on {self.created_at.date()}"


class Popup(models.Model):
    title = models.CharField(max_length=200)
    message = models.TextField()
    link_url = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=False)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    def is_visible(self):
        now = timezone.now()
        if not self.is_active:
            return False
        if self.start_date and now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        return True
    


class UserActivity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=255)
    path = models.CharField(max_length=255, null=True, blank=True)
    method = models.CharField(max_length=10, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} - {self.action} at {self.method} {self.timestamp}"
    