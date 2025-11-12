from django.contrib import admin
from .models import *
# Register your models here.

admin.site.register(Interest)
admin.site.register(Loanable)
admin.site.register(Investment)
admin.site.register(InterestAmount)



@admin.register(Savings)
class SavingsAdmin(admin.ModelAdmin):
    
    search_fields = (
    'month',
    'member__member__first_name',
    'member__member__last_name',
    'member__member__member_number',
    'member__ippis',
)
    list_display = ('member__member__first_name', 'member__member__last_name', 'member__ippis', 'month', 'month_saving', 'original_amount', 'date_created')

@admin.register(DeleteLog)
class DeleteLogAdmin(admin.ModelAdmin):
    list_display = ("user", "action", "month", "records_deleted", "timestamp")
    list_filter = ("action", "month", "user")
    search_fields = ("user__username", "remarks")
