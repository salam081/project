from django.urls import path
from .import views

urlpatterns = [
    
    path("payment-types/", views.payment_type_list, name="payment_type_list"),
    path("payment-types/create/", views.payment_type_create, name="payment_type_create"),
    path("payment-types/<int:pk>/edit/", views.payment_type_edit, name="payment_type_edit"),
    path("payment-types/<int:pk>/delete/", views.payment_type_delete, name="payment_type_delete"),

    path("payments/", views.request_form_payment_list, name="request_form_payment_list"),
    path("payments/create/", views.request_form_payment_create, name="request_form_payment_create"),
    path("payments/<int:pk>/", views.request_form_payment_detail, name="request_form_payment_detail"),
    path("payments/<int:pk>/delete/", views.request_form_payment_delete, name="request_form_payment_delete"),
    path("payments/export/pdf/", views.request_form_payment_export_pdf, name="request_form_payment_export_pdf"),
    path("payments/export/", views.request_form_payment_export_excel, name="request_form_payment_export"),

]