from django.urls import path 
from .import views 


urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/',views.admin_dashboard,name="admin_dashboard"),
    path('staff-dashboard/',views.staff_dashboard,name="staff_dashboard"),

    path('financial_list/', views.list_financial_summaries, name='financial_list'),
    path('financial-summary/delete/<int:pk>/', views.delete_financial_summary, name='delete_financial_summary'),
    
    # path("cooperative_summary/", views.cooperative_summary, name="cooperative_summary"),
    path('list_withdrawal_requests/', views.list_withdrawal_requests, name='list_withdrawal_requests'),
    path('approve/<int:pk>/', views.approve_withdrawal_request, name='approve_withdrawal_request'),
    path('decline/<int:pk>/', views.decline_withdrawal_request, name='decline_withdrawal_request'),
    path('eligible-members/', views.eligible_members_view, name='eligible_members_view'),
    
    # path('partial-withdrawals/', views.partial_withdrawals_list, name='partial_withdrawals_list'),
    # path('partial-withdrawals/<int:pk>/approve/', views.approve_withdrawal_request, name='partial_approve_withdrawal_request'),
    # path('partial-withdrawals/<int:pk>/decline/', views.decline_withdrawal_request, name='partial_decline_withdrawal_request'),
    
    path('partial-withdrawals/', views.partial_withdrawals_list, name='partial_withdrawals_list'),
    path('withdrawals/<int:pk>/', views.partial_withdrawal_detail, name='partial_withdrawal_detail'),
    path('withdrawals/<int:pk>/approve/', views.partial_withdrawal_approve, name='partial_withdrawal_approve'),
    path('withdrawals/<int:pk>/decline/', views.partial_withdrawal_decline, name='partial_withdrawal_decline'),
    path('withdrawals/bulk-action/', views.partial_withdrawal_bulk_action, name='partial_withdrawal_bulk_action'),
    
    path("guest/request/", views.guest_request_consumable, name="guest_request_consumable"),
    path("active-requests/", views.member_active_requests, name="member_active_requests"),
    path("upload_opening_balances/", views.upload_opening_balances, name="upload_opening_balances"),
    path("loan-totals/", views.loan_totals, name="loan_totals"),


    path("distribute_dividends/", views.dividend_report, name="distribute_dividends"),
    path("dividendlist/", views.list_dividend_rounds, name="dividend_list"),
    path('dividend/delete-round/<str:profit_amount>/', views.delete_dividend_round_bulk, name='delete_dividend_round'),

    # path("landing_page/", views.landing_page, name="landing_page"),
   
    path("popup_form", views.popup_message_form, name="popup_form"),
    path("active-summary/<int:pk>/", views.member_active_summary, name="member_active_summary"),
   
   
    path('user_activity/', views.user_activity_list, name='user_activity_list'),
    path('user_activity/delete/<int:pk>/', views.delete_user_activity, name='delete_user_activity'),

]
