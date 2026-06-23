from django.contrib import admin
from .models import *
# Register your models here.
# admin.site.register(LoanRequest)
admin.site.register(LoanType)
admin.site.register(BankName)
admin.site.register(BankCode)
admin.site.register(LoanSettings)
# admin.site.register(LoanRequestFee)


@admin.register(LoanRequest)
class LoanRequestAdmin(admin.ModelAdmin):
    search_fields = (
        'member__member__first_name',
        'member__member__last_name',
        'member__member__member_number',
        'member__ippis',
    )
   
    list_display = (
       'member', 'amount','approved_amount','status','approved_by','guarantor' 
       
    )
    
@admin.register(LoanRequestFee) 
class LoanRequestFeeAdmin(admin.ModelAdmin):
    search_fields = (
        'member__member__first_name',
        'member__member__last_name',
        'member__ippis',
    )
    
    list_display = (
        'member',
        'loan_type',
        'status',
        'form_fee',
    )
        
@admin.register(LoanRepayback)
class LoanRepaybackAdmin(admin.ModelAdmin):
    search_fields = ('loan_request','repayment_date','amount_paid','balance_remaining','created_by')
    list_display = ('loan_request','repayment_date','amount_paid','balance_remaining','created_by')

