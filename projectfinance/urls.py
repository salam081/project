from django.urls import path
from .import views
urlpatterns = [
    path('application_list/', views.application_list_view, name='application_list'),
    path('application/<int:application_id>/', views.application_detail_view, name='application_detail'),
    # path('review-application/<int:id>/', views.review_application, name='review_application'),

    path('project-finance-requests/', views.admin_project_finance_requests_list, name='admin_project_finance_requests'),
    path('project_finance_approved/<id>/', views.admin_approve_finance_request, name='project_finance_approved'),
    
    # path('review-project-finance/<int:request_id>/', views.review_project_finance_request, name='review_project_finance_request'),
    

    path('project-finance/', views.project_finance_report_view, name='project_finance_report'),
    path('project-finance/report/api/', views.project_finance_report_api, name='project_finance_report_api'),
    path('project-finance/report/excel/', views.project_finance_report_excel, name='project_finance_report_excel'),
    path('upload-payments/', views.upload_project_finance_repayment, name='upload_project_finance_payment'),

]
