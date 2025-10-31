from django.contrib import admin
from .models import *
# Register your models here.
# admin.site.register(LoanRequest)
admin.site.register(LoanRepayback)
admin.site.register(LoanType)
admin.site.register(BankName)
admin.site.register(BankCode)
admin.site.register(LoanSettings)
admin.site.register(LoanRequestFee)


@admin.register(LoanRequest)
class LoanRequestAdmin(admin.ModelAdmin):
    search_fields =(
        'member','amount','approved_amount','status','approved_by'    
    )
    list_display = (
        'member','amount','approved_amount','status','approved_by','approval_date','guarantor' 
    )
