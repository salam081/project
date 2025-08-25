from django.urls import path 
from .import views 


urlpatterns = [
    path('member_dashboard/',views.member_dashboard,name="member_dashboard"),
    path('member_savings/',views.member_savings,name="member_savings"),
    path('ajax/load-bank-code/', views.ajax_load_bank_code, name='ajax_load_bank_code'),

    path('loan_request/',views.loan_request_view,name="loan_request"),
    path('guarantor/<int:pk>/', views.show_guarantor_approval, name='guarantor_approval_page'),
    path('guarantor/confirm/<int:pk>/', views.confirm_guarantor_approval, name='confirm_guarantor_approval'),
     path('my_loan_requests/', views.my_loan_requests, name='my_loan_requests'),
    path('loan_details/<int:request_id>/', views.member_loan_request_detail, name='member_loan_request_detail'),


    path('request/', views.request_consumable, name='request_consumable'),
    path('my_consumablerequests', views.my_consumable_requests, name='my_consumablerequests'),
    path('request_detail/<int:request_id>/', views.request_detail, name='request_detail'),
    path('cancel_consumable_request/<int:id>/', views.cancel_consumable_request, name='cancel_consumable_request'),
    path('member-withdrawal/', views.member_withdrawal_request, name='member_withdrawal_request'),

    path('project-finance-list/',views.project_finance_application_list,name='project_finance_application_list'),
    path('project-finance-update/<int:id>/',views.update_project_finance_application,name='update_project_finance_application'),
    path('project_finance',views.project_finance_application,name='project_finance_application'),
    path('create_project_finance/<int:id>/',views.create_project_finance_request,name='create_project_finance_request'),
    path('approve_guarantor_request/<int:id>/',views.approve_guarantor_request,name='approve_guarantor_request'),

    
]