from django.contrib import admin
from .models import *
# Register your models here.

@admin.register(SpecialSavings)
class SpecialSavingsAdmin(admin.ModelAdmin):
    list_display = ("member", "month", "month_savings", "date_created", "created_by")
    list_filter = ("month", "created_by")
    search_fields = ("member__member__first_name", "member__member__last_name", "member__ippis")
   
   
@admin.register(TargetSavings)
class TargetSavingsAdmin(admin.ModelAdmin):
    list_display = ("member", "month", "month_savings", "date_created", "created_by")
    list_filter = ("month", "created_by")
    search_fields = ("member__member__first_name", "member__member__last_name", "member__ippis")
   
    
@admin.register(SpecialSavingsTergetSavingsRequestForm)
class SpecialSavingsRequestAdmin(admin.ModelAdmin):
    list_display = ("member","amount","savings_type","date_created")  
 
    
admin.site.register(SavingType)  
admin.site.register(TargetSavingsWithdrawal)  
