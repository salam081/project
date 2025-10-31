from django.contrib import admin
from .models import *
# Register your models here.
admin.site.register(State)
admin.site.register(Address)
admin.site.register(Member)
admin.site.register(UserGroup)
admin.site.register(Gender)
admin.site.register(Religion)
admin.site.register(NextOfKin)
admin.site.register(MaritalStatus)


class UserAdmin(admin.ModelAdmin):
    
    search_fields = ('first_name','last_name')
admin.site.register(User,UserAdmin)


@admin.register(PagePermission)
class PagePermissionAdmin(admin.ModelAdmin):
    list_display = ('group', 'page', 'allowed')
    list_filter = ('group', 'page')
    

