from django.contrib import admin
from .models import *
# Register your models here.
admin.site.register(ConsumableRequest)
admin.site.register(ConsumableRequestDetail)
admin.site.register(PaybackConsumable)
admin.site.register(ConsumableType)
admin.site.register(ConsumableFormFee)

class ItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'price', 'quantity_in_stock', 'total_stock_value')

    def total_stock_value(self, obj):
        return obj.price * obj.quantity_in_stock
    total_stock_value.short_description = 'Total Value'

admin.site.register(Item, ItemAdmin)