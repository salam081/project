from django.urls import path 
from .import views 


urlpatterns = [
    path('dashboard/',views.admin_dashboard,name="admin_dashboard"),

    path('financial_list/', views.list_financial_summaries, name='financial_list'),
    path('financial-summary/delete/<int:pk>/', views.delete_financial_summary, name='delete_financial_summary'),
    
    path("cooperative_summary/", views.cooperative_summary, name="cooperative_summary"),
    path('list_withdrawal_requests/', views.list_withdrawal_requests, name='list_withdrawal_requests'),
    path('approve/<int:pk>/', views.approve_withdrawal_request, name='approve_withdrawal_request'),
    path('decline/<int:pk>/', views.decline_withdrawal_request, name='decline_withdrawal_request'),
    path('eligible-members/', views.eligible_members_view, name='eligible_members_view'),
   
    
]