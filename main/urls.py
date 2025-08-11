from django.urls import path 
from .import views 


urlpatterns = [
    path('dashboard/',views.admin_dashboard,name="admin_dashboard"),

    path('financial_list/', views.list_financial_summaries, name='financial_list'),
    path('financial-summary/delete/<int:pk>/', views.delete_financial_summary, name='delete_financial_summary'),
   
    
]