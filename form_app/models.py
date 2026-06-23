from django.db import models
from accounts.models import *


# Create your models here.
class PaymentType(models.Model):
    title = models.CharField(max_length=100)
    request_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    available = models.BooleanField(default=True)
    
    def __str__(self):
        return self.title

class RequestFormPayment(models.Model):
    STATUS_CHOICES = (("paid", "Paid"),("used", "Used"),)
    payment_type = models.ForeignKey("PaymentType",on_delete=models.CASCADE)
    member = models.ForeignKey("accounts.Member",on_delete=models.CASCADE,null=True,blank=True)
    guest_name = models.CharField(max_length=200, null=True, blank=True)
    guest_ippis = models.CharField(max_length=50, null=True, blank=True)
    guest_phone = models.CharField(max_length=20, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2,blank=True, null=True)
    duration = models.CharField(max_length=50, null=True,blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="paid")
    created_by = models.ForeignKey(User,on_delete=models.SET_NULL, null=True,blank=True,related_name="created_payments")
    date_created = models.DateTimeField(auto_now_add=True)   
    
    def __str__(self):
        return f"{self.payment_type} - {self.amount} - {self.status} - {self.member or self.guest_name}"
 