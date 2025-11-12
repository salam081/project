from django.urls import path
from . import views



urlpatterns = [
    # Dashboard
    path('purchasedashboard/', views.purchase_consumable_dashboard, name='purchase_consumable_dashboard'),
    path('consumable_request_list/', views.consumable_purchase_request_list, name='consumable_purchase_request_list'),

    path('requests/create/', views.consumable_purchase_request_create, name='consumable_purchase_request_create'),
    path('request_edit/<int:pk>/', views.consumable_request_edit, name='consumable_request_edit'),
    path('requests/<int:pk>/', views.consumable_purchase_request_detail, name='consumable_purchase_request_detail'),
    path('purchase_request_review/<int:pk>/', views.consumable_purchase_review, name='consumable_purchase_review'),
    path('requests/<int:pk>/approve/', views.consumable_purchase_approve, name='consumable_purchase_approve'),

    
    path('requests/<int:request_pk>/items/add/', views.purchased_item_create, name='purchased_item_create'),
    path('purchased_item_list/', views.purchased_item_list, name='purchased_item_list'),
    path('purchased_item/<int:pk>/', views.purchased_item_detail, name='purchased_item_detail'),
    path('purchased_item/<int:pk>/edit/', views.purchased_item_edit, name='edit_purchased_item'),
    path('purchased_item/<int:pk>/delete/', views.purchased_item_delete, name='delete_purchased_item'),
    



    path('items/<int:item_pk>/selling-plan/create/', views.selling_plan_create, name='selling_plan_create'),
    path('selling-plans/', views.selling_plan_list, name='selling_plan_list'),
    path('selling-plans/<int:pk>/', views.selling_plan_detail, name='selling_plan_detail'),
    path('selling-plans/<int:pk>/edit/', views.selling_plan_edit, name='selling_plan_edit'),
    path('selling-plans/<int:pk>/delete/', views.selling_plan_delete, name='selling_plan_delete'),

    path('requests/<int:pk>/mark-accounted/', views.consumable_request_mark_accounted, name='consumable_request_mark_accounted'),
    path('requests/account/<int:pk>/', views.refund_and_account_request, name='refund_and_account_request'),

    path('items/<int:pk>/selling-plan/create/', views.selling_plan_create, name='selling_plan_create'),
    path('selling-plans/<int:pk>/delete/', views.selling_plan_delete, name='selling_plan_delete'),
    
]