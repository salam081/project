from django.contrib import admin
from .models import *
# Register your models here.

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'address')
    
@admin.register(StockIn)
class StockInAdmin(admin.ModelAdmin):
    list_display = ('supplier', 'received_at', 'note', 'get_total_cost')
    readonly_fields = ('received_at',)
    
@admin.register(ReceivedItem)
class ReceivedItemAdmin(admin.ModelAdmin):
    list_display = ('stock_in', 'brand', 'model_name', 'quantity', 'unit_price', 'total_price')
    
admin.site.register(SellingPlan)
# admin.site.register(BatchType)
admin.site.register(MemberRequest)  
admin.site.register(MemberRequestDetail)
admin.site.register(MemberRequestPayback)  
    

