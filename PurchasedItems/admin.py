
from django.contrib import admin
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.contrib import admin
from django.db.models import F, Sum, DecimalField
from django.db.models.functions import Coalesce

from .models import (
    ConsumablePurchasedRequest,
    PurchasedItem,
    SellingPlan,
    PurchasedItemAdjustment,
    SellingPlanAdjustment,
)


class PurchasedItemInline(admin.TabularInline):
    """Inline for purchased items in request admin"""
    model = PurchasedItem
    extra = 0
    fields = ('item_name', 'quantity', 'unit_price', 'expenditure_amount', 'total_price_display')
    readonly_fields = ('total_price_display',)
    
    def total_price_display(self, obj):
        """Display total price for the item"""
        if obj.pk:
            return f"₦{obj.total_price:,.2f}"
        return "-"
    total_price_display.short_description = "Total Price"


class PurchasedItemAdjustmentInline(admin.TabularInline):
    """Inline for purchased item adjustments"""
    model = PurchasedItemAdjustment
    extra = 0
    fields = ('old_price', 'new_price', 'reason', 'adjusted_by', 'date_adjusted')
    readonly_fields = ('date_adjusted',)


class SellingPlanAdjustmentInline(admin.TabularInline):
    """Inline for selling plan adjustments"""
    model = SellingPlanAdjustment
    extra = 0
    fields = ('old_price', 'new_price', 'reason', 'adjusted_by', 'date_adjusted')
    readonly_fields = ('date_adjusted',)


admin.site.register(ConsumablePurchasedRequest)


admin.site.register(PurchasedItem)

admin.site.register(SellingPlan)

admin.site.register(PurchasedItemAdjustment)

@admin.register(SellingPlanAdjustment)
class SellingPlanAdjustmentAdmin(admin.ModelAdmin):
    """Admin interface for SellingPlanAdjustment"""
    
    list_display = (
        'selling_plan_link', 'old_price', 'new_price', 'price_change_display',
        'adjusted_by', 'date_adjusted'
    )
    list_filter = ('date_adjusted', 'adjusted_by')
    search_fields = ('selling_plan__purchased_item__item_name', 'reason', 'adjusted_by__username')
    readonly_fields = ('date_adjusted', 'price_change_display')
    
    fieldsets = (
        ('Adjustment Information', {
            'fields': ('selling_plan', 'old_price', 'new_price', 'reason')
        }),
        ('Meta Information', {
            'fields': ('adjusted_by', 'date_adjusted', 'price_change_display'),
            'classes': ('collapse',)
        }),
    )
    
    def selling_plan_link(self, obj):
        """Display link to selling plan"""
        url = reverse('admin:consumable_sellingplan_change', 
                     args=[obj.selling_plan.pk])
        return format_html('<a href="{}">{}</a>', url, 
                          obj.selling_plan.purchased_item.item_name)
    selling_plan_link.short_description = 'Selling Plan'
    
    def price_change_display(self, obj):
        """Display price change with direction indicator"""
        change = obj.new_price - obj.old_price
        if change > 0:
            return format_html(
                '<span style="color: #28a745;">+₦{:,.2f}</span>',
                change
            )
        elif change < 0:
            return format_html(
                '<span style="color: #dc3545;">-₦{:,.2f}</span>',
                abs(change)
            )
        return "₦0.00"
    price_change_display.short_description = 'Price Change'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related(
            'selling_plan__purchased_item', 'adjusted_by'
        )


# Custom admin site configuration
admin.site.site_header = "Consumable Management Admin"
admin.site.site_title = "Consumable Admin"
admin.site.index_title = "Welcome to Consumable Management"