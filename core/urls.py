
from django.contrib import admin
from django.urls import path,include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('accounts.urls')),
    path('', include('main.urls')),
    path('', include('loan.urls')),
    path('consumables/', include('consumable.urls')),
    
    path('member/', include('member.urls')),
    path('savings/', include('savings.urls')),
    path('', include('PurchasedItems.urls')),
    path('', include('report.urls')),
    path('', include('projectfinance.urls')),
]
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

