from django.contrib import admin
from .models import *
# Register your models here.

admin.site.register(Interest)
admin.site.register(Loanable)
admin.site.register(Investment)
admin.site.register(InterestAmount)



class SavingsAdmin(admin.ModelAdmin):
    
    search_fields = (
    'month',
    'member__member__first_name',
    'member__member__last_name',
    'member__member__member_number',
    'member__ippis',
)
admin.site.register(Savings,SavingsAdmin)

# admin.site.register(Savings)