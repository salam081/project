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
    
    path("guest/request/", views.guest_request_consumable, name="guest_request_consumable"),
    path("active-requests/", views.member_active_requests, name="member_active_requests"),
    path("upload_opening_balances/", views.upload_opening_balances, name="upload_opening_balances"),
    path("loan-totals/", views.loan_totals, name="loan_totals"),


    path("distribute_dividends/", views.dividend_report, name="distribute_dividends"),
   
]
