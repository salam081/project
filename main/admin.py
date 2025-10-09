from django.contrib import admin
from .models import *
# Register your models here.
admin.site.register(FinancialSummary)
admin.site.register(Withdrawal)
admin.site.register(Dividend)




@admin.register(Popup)
class PopupAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active", "start_date", "end_date", "created_at")
    list_editable = ("is_active",)
    list_filter = ("is_active",)
    ordering = ("-created_at",)


