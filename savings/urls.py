from django.urls import path
from .import views

urlpatterns = [
    path('upload-savings/',  views.upload_savings, name='upload_savings'),
    path('subscription-fee/',  views.subscription_fee, name='subscription_fee'),
    path('edit_subscription_fee/<int:id>/',  views.edit_subscription_fee, name='edit_subscription_fee'),
    path("monthly-uploads/", views.monthly_savings_uploads, name="monthly_savings_uploads"),
    path("monthly-uploads/<str:month>/", views.view_monthly_savings, name="view_monthly_savings"),
    path('delete-savings/',  views.delete_monthly_savings, name='delete_monthly_savings'),
    path("savings/<int:saving_id>/edit/", views.edit_saving, name="edit_saving"),
    path('saving-report/', views.report_view, name='saving_report'),
    path('search_member_savings/', views.search_member_for_savings, name='search_member'),
    path('member/<int:id>/add_savings/', views.process_member_savings, name='add_individual_savings'),
    # path('member/<int:id>/add_savings/', views.add_individual_member_savings, name='add_individual_savings'),

    
    # path("interest_form/", views.interest_form_view, name='interest_form'),
    # path('deduct_interest/', views.deduct_monthly_interest, name='deduct_interest'),

    # path('distribute/', views.distribute_savings_form, name='distribute_savings'),
    # path('distribute_savings/<int:year>/<int:month>/', views.distribute_savings_view, name='distribute_savings'),

    path('all_member_saving_search/',views.all_member_saving_search,name='all_member_saving_search'),
    path('list-savings/', views.list_savings, name='list_savings'),
]