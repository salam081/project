from django.urls import path
from . import views


urlpatterns = [
    # ─── BUDGET URLS ───────────────────────────────────────────
    path('ram_dashboard/', views.ram_dashboard, name='ram_dashboard'),
    path("budget_list/", views.budget_list, name="budget_list"),
    path("budget/toggle/<int:pk>/", views.toggle_budget_status, name="toggle_budget_status"),
    path("budget_create/", views.budget_create, name="budget_create"),
    path("budgets/<int:pk>/", views.budget_detail, name="budget_detail"),
    path("budget_update/<int:pk>/update/", views.budget_update, name="budget_update"),
    path("budgets/<int:pk>/approve/", views.budget_approve, name="budget_approve"),
    path("budgets/<int:pk>/reject/", views.budget_reject, name="budget_reject"),

    # ─── RAM REQUEST URLS ──────────────────────────────────────
    path("ram_request_list/", views.ram_request_list, name="ram_request_list"),
    path("ram_request_create/", views.ram_request_create, name="ram_request_create"),
    path("ram_request_detail/<int:pk>/", views.ram_request_detail, name="ram_request_detail"),
    path("ram_request_approve/<int:pk>/approve/", views.ram_request_approve, name="ram_request_approve"),
    path("ram_request_reject/<int:pk>/reject/", views.ram_request_reject, name="ram_request_reject"),

    # ─── PAYMENT URLS ──────────────────────────────────────────
    path("ram_request_payments/<int:pk>/payment/add/", views.payment_add, name="payment_add"),
    path("ram_request_payments/<int:pk>/payments/", views.payment_list, name="ram_request_payment_list"),
    path("ram-payment-upload/", views.payment_upload, name="payment_upload"),
    path("ram-payment-list/", views.ram_payment_list, name="ram_payment_list"),
]