from django.contrib import admin
from .models import *
from .models import PurchasedItemAdjustment, SellingPlanAdjustment, PurchasedItem, SellingPlan

# Register your models here.
admin.site.register(ConsumablePurchasedRequest)
# admin.site.register(PurchasedItem)
# admin.site.register(SellingPlan)



# 1️⃣ Register PurchasedItemAdjustment
@admin.register(PurchasedItemAdjustment)
class PurchasedItemAdjustmentAdmin(admin.ModelAdmin):
    list_display = ('purchased_item', 'old_price', 'new_price', 'adjusted_by', 'date_adjusted', 'reason')
    list_filter = ('date_adjusted', 'adjusted_by')
    search_fields = ('purchased_item__item_name', 'adjusted_by__username', 'reason')
    readonly_fields = ('date_adjusted',)


# 2️⃣ Register SellingPlanAdjustment
@admin.register(SellingPlanAdjustment)
class SellingPlanAdjustmentAdmin(admin.ModelAdmin):
    list_display = ('selling_plan', 'old_price', 'new_price', 'adjusted_by', 'date_adjusted', 'reason')
    list_filter = ('date_adjusted', 'adjusted_by')
    search_fields = ('selling_plan__purchased_item__item_name', 'adjusted_by__username', 'reason')
    readonly_fields = ('date_adjusted',)


# Optional: Inline adjustments under PurchasedItem
class PurchasedItemAdjustmentInline(admin.TabularInline):
    model = PurchasedItemAdjustment
    extra = 0
    readonly_fields = ('date_adjusted',)
    can_delete = False


@admin.register(PurchasedItem)
class PurchasedItemAdmin(admin.ModelAdmin):
    list_display = ('item_name', 'unit_price', 'quantity')
    inlines = [PurchasedItemAdjustmentInline]


# Optional: Inline adjustments under SellingPlan
class SellingPlanAdjustmentInline(admin.TabularInline):
    model = SellingPlanAdjustment
    extra = 0
    readonly_fields = ('date_adjusted',)
    can_delete = False


@admin.register(SellingPlan)
class SellingPlanAdmin(admin.ModelAdmin):
    list_display = ('purchased_item', 'selling_price_per_unit', 'quantity', 'profit', 'available')
    inlines = [SellingPlanAdjustmentInline]
