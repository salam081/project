from django.urls import path
from .import views
urlpatterns = [
   path('savings_request_form_payment/',  views.savings_request_form_payment, name='savings_request_form_payment'),
   # path('all_special_savings_request/',  views.all_special_savings_request, name='all_special_savings_request'),

   path('upload_special_savings/',  views.upload_special_savings, name='upload_special_savings'),
   path("create_special_savings/", views.admin_create_special_savings, name="create_special_savings"),
   path('special_savings_list/',  views.special_savings_list, name='special_savings_list'),
   path('monthly-detail/<int:year>/<int:month>/', views.monthly_special_savings_detail, name='monthly_detail'),
   path('delete-monthly/<int:year>/<int:month>/', views.delete_monthly_savings, name='delete_monthly'),
   
   # Target Savings URLs
   path('upload_target_savings/',  views.upload_target_savings, name='upload_target_savings'),
   path("create_target_savings/", views.create_target_savings, name="create_target_savings"),
   path('target_savings_list/',  views.target_savings_list, name='target_savings_list'),
   path('target-monthly-detail/<int:year>/<int:month>/', views.monthly_target_savings_detail, name='target_monthly_detail'),
   path('delete-target-monthly/<int:year>/<int:month>/', views.delete_monthly_target_savings, name='delete_target_monthly'),
   
   
   path("special-savings_withdrawals/",views.admin_special_savings_withdrawals, name="admin_special_savings_withdrawals",),
   path("review-special-savings-withdrawal/<int:pk>/",views.review_special_savings_withdrawal, name="review_special_savings_withdrawal",),
    
    
    path("target-savings_withdrawals/",views.admin_target_savings_withdrawals, name="admin_target_savings_withdrawals",),
    path("target-savings/withdrawals/<int:pk>/",views.review_target_savings_withdrawal,name="review_target_savings_withdrawal",),
]