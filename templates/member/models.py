from django.db import models
from django.contrib.auth.models import AbstractUser
from django_countries.fields import CountryField
from savings.models import Savings, Loanable, Investment
from decimal import Decimal

# Create your models here.



class UserGroup(models.Model):
    title = models.CharField(max_length=50)

    def __str__(self):
        return self.title
    
class Gender(models.Model):
    title = models.CharField(max_length=150)

    def __str__(self):
        return self.title
    
class MaritalStatus(models.Model):
    title = models.CharField(max_length=150)

    def __str__(self):
        return self.title

class Religion(models.Model):
    title = models.CharField(max_length=150)

    def __str__(self):
        return self.title

    
class User(AbstractUser):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    other_name = models.CharField(max_length=100,blank=True,null=True)
    date_of_birth = models.DateField(blank=True,null=True)
    username = models.CharField(max_length=100, unique=True)
    savings = models.IntegerField(blank=True,null=True)
    account_type = models.CharField(max_length=100,blank=True,null=True)
    department = models.CharField(max_length=100)
    unit = models.CharField(max_length=100,blank=True,null=True)
    gender = models.ForeignKey(Gender, on_delete=models.CASCADE, blank=True, null=True)
    group = models.ForeignKey(UserGroup, on_delete=models.CASCADE, blank=True, null=True)
    marital_status = models.ForeignKey(MaritalStatus,on_delete=models.SET_NULL, null=True, blank=True)
    religion = models.ForeignKey(Religion, on_delete=models.SET_NULL, null=True, blank=True,)
    passport = models.ImageField(upload_to='passport', blank=True, null=True)
    phone1 = models.CharField(max_length=15,null=True, blank=True)
    phone2 = models.CharField(max_length=15, null=True, blank=True)
    email = models.EmailField(blank=True, null=True)
    member_number = models.CharField(max_length=100) 


    def __str__(self):
        return f"{self.first_name} ({self.last_name})"
    

class Member(models.Model):
    member = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True,related_name='member')
    ippis = models.IntegerField(unique=True)  # Required and unique
    total_savings = models.DecimalField(max_digits=12, decimal_places=2, default=0, blank=True, null=True)
    total_profit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
     # Special savings
    total_special_savings = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_target_savings = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.member} ({self.ippis})"

    def update_total_savings(self):
        total = self.savings.aggregate(models.Sum("month_saving"))["month_saving__sum"] or 0.00

        # total = self.savings_set.aggregate(models.Sum("month_saving"))["month_saving__sum"] or 0.00
        self.total_savings = total

        # Reset profit if savings is 0
        if total == 0:
            self.total_profit = 0

        self.save()
        
    # # Special savings updater
    # def update_special_savings(self):
    #     total = self.special_savings.aggregate(total=models.Sum("month_savings"))["total"] or Decimal("0.00")

    #     self.total_special_savings = total
    #     self.save(update_fields=["total_special_savings"])
            
    # # Special savings updater
    # def update_target_savings(self):
    #     total = self.target_savings.aggregate(total=models.Sum("month_savings"))["total"] or Decimal("0.00")

    #     self.total_target_savings = total
    #     self.save(update_fields=["total_target_savings"])
        
    def update_special_savings(self):
        from django.db.models import Sum
        
        total_saved = self.special_savings.aggregate(
            total=Sum("month_savings")
        )["total"] or Decimal("0.00")

        total_withdrawn = self.special_savings_withdrawals.filter(
            status="approved"
        ).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0.00")

        self.total_special_savings = total_saved - total_withdrawn
        self.save(update_fields=["total_special_savings"])
        
        
        
    def update_target_savings(self):
        from django.db.models import Sum
        
        total_saved = self.target_savings.aggregate(
            total=Sum("month_savings")
        )["total"] or Decimal("0.00")

        total_withdrawn = self.target_savings_withdrawals.filter(
            status="approved"
        ).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0.00")

        self.total_target_savings = total_saved - total_withdrawn
        self.save(update_fields=["total_target_savings"])
                        
    # Add this method to your existing Member model
    def get_complete_financial_data(self):
        """Get complete financial data for the member"""
        
        
        # Get all savings
        savings = Savings.objects.filter(member=self).order_by('-month')
        total_savings = savings.aggregate(total=models.Sum('month_saving'))['total'] or Decimal('0.00')
        
    
        # Get all loanable
        loanable = Loanable.objects.filter(member=self).order_by('-month')
        total_loanable = loanable.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        
        # Get all investment
        investment = Investment.objects.filter(member=self).order_by('-month')
        total_investment = investment.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
        
        return {
            'savings': savings,
            
            'loanable': loanable,
            'investment': investment,
            'total_savings': total_savings,
            'total_loanable': total_loanable,
            'total_investment': total_investment,
            'grand_total': total_savings  + total_loanable + total_investment
        }

class State(models.Model):
    title = models.CharField(max_length=150)
   

    def __str__(self):
        return self.title

class Address(models.Model):
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True)
    country = models.CharField(max_length=200, blank=True, null=True)
    state_of_origin = models.ForeignKey('State', on_delete=models.SET_NULL, null=True, blank=True)
    local_government_area = models.CharField(max_length=250)
    address = models.CharField(max_length=500)


    def __str__(self):
        return str(self.user)  
        

class NextOfKin(models.Model):
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True)
    full_names = models.CharField(max_length=150)
    phone_no = models.CharField(max_length=115) 
    address = models.CharField(max_length=500)  
    email = models.EmailField()
    netofkin_passport = models.ImageField(upload_to='netofkin_passport', blank=True, null=True)

    def __str__(self):
        return f"{self.full_names} ({self.phone_no})"    
    
    

class PagePermission(models.Model):
    group = models.ForeignKey(UserGroup, on_delete=models.CASCADE)
    page = models.CharField(max_length=100)
    allowed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.group.title} - {self.page}"
              

