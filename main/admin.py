from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from .models import *
# Register your models here.
admin.site.register(FinancialSummary)
admin.site.register(Withdrawal)
admin.site.register(PartialWithdrawal)
admin.site.register(Dividend)




# @admin.register(Popup)
# class PopupAdmin(admin.ModelAdmin):
#     list_display = ("title", "is_active", "start_date", "end_date", "created_at")
#     list_editable = ("is_active",)
#     list_filter = ("is_active",)
#     ordering = ("-created_at",)
    
@admin.register(Popup)
class PopupAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'start_date', 'end_date', 'status_badge', 'preview_link')
    list_filter = ('is_active',)
    search_fields = ('title', 'message')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)

    def status_badge(self, obj):
        """Display popup visibility status with color badge."""
        now = timezone.now()

        if not obj.is_active:
            color = "gray"
            label = "Inactive"
        elif obj.start_date and now < obj.start_date:
            color = "orange"
            label = "Upcoming"
        elif obj.end_date and now > obj.end_date:
            color = "red"
            label = "Expired"
        else:
            color = "green"
            label = "Active"

        return format_html(
            f'<span style="color: white; background-color: {color}; padding: 3px 8px; '
            f'border-radius: 5px; font-size: 12px;">{label}</span>'
        )
    status_badge.short_description = "Status"

    def preview_link(self, obj):
        """Optional link to quickly preview the popup URL."""
        if obj.link_url:
            return format_html('<a href="{}" target="_blank">🔗 Visit</a>', obj.link_url)
        return "-"
    preview_link.short_description = "Link"

    def save_model(self, request, obj, form, change):
        """Auto-deactivate expired popups on save."""
        if obj.end_date and obj.end_date < timezone.now():
            obj.is_active = False
        super().save_model(request, obj, form, change)    
    
    
@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'path', 'method', 'timestamp', 'ip_address')
    list_filter = ('user', 'method')
    search_fields = ('user__username', 'action', 'path', 'ip_address')    


