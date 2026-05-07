from django.contrib import admin
from .models import *
# Register your models here.



admin.site.register(Interest)
# admin.site.register(Loanable)
# admin.site.register(Investment)
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

    list_display = (
        'first_name',
        'last_name',
        'member_ippis',
        'month',
        'month_saving',
        'original_amount',
        'date_created',
    )

    # Methods for list_display
    def first_name(self, obj):
        return obj.member.member.first_name

    def last_name(self, obj):
        return obj.member.member.last_name

    def member_ippis(self, obj):
        return obj.member.ippis

    # Optional: nicer column headers
    first_name.short_description = 'First Name'
    last_name.short_description = 'Last Name'
    member_ippis.short_description = 'IPPIS'



@admin.register(Loanable)
class LoanableAdmin(admin.ModelAdmin):
    
    search_fields = (
        'month',
        'member__member__first_name',
        'member__member__last_name',
        'member__member__member_number',
        'member__ippis',
    )

    list_display = (
        'first_name',
        'last_name',
        'member_ippis',
        'month',
        'amount',
        'total_amount',
        'date_created',
    )

    # Methods for list_display
    def first_name(self, obj):
        return obj.member.member.first_name

    def last_name(self, obj):
        return obj.member.member.last_name

    def member_ippis(self, obj):
        return obj.member.ippis

    # Optional: nicer column headers
    first_name.short_description = 'First Name'
    last_name.short_description = 'Last Name'
    member_ippis.short_description = 'IPPIS'
    


@admin.register(Investment)
class InvestmentAdmin(admin.ModelAdmin):
    
    search_fields = (
        'month',
        'member__member__first_name',
        'member__member__last_name',
        'member__member__member_number',
        'member__ippis',
    )

    list_display = (
        'first_name',
        'last_name',
        'member_ippis',
        'month',
        'amount',
        'total_amount',
        'date_created',
    )

    # Methods for list_display
    def first_name(self, obj):
        return obj.member.member.first_name

    def last_name(self, obj):
        return obj.member.member.last_name

    def member_ippis(self, obj):
        return obj.member.ippis

    # Optional: nicer column headers
    first_name.short_description = 'First Name'
    last_name.short_description = 'Last Name'
    member_ippis.short_description = 'IPPIS'
    
        
@admin.register(DeleteLog)
class DeleteLogAdmin(admin.ModelAdmin):
    list_display = ("user", "action", "month", "records_deleted", "timestamp")
    list_filter = ("action", "month", "user")
    search_fields = ("user__username", "remarks")
