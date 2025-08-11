from django.urls import path
from . import views

urlpatterns = [
    path('consumable_dashboard/', views.consumable_dashboard, name='consumable_dashboard'),
    path('consumable_fee/', views.consumable_fee, name='consumable_fee'),
    path('consumable_items/', views.consumable_items, name='consumable_items'),
    path('delete_item/<id>/', views.delete_item, name='delete_item'),

    path('admin_consumables_list',views.admin_consumables_list,name='admin_consumables_list'),
    path('consumables/<int:request_id>/', views.admin_consumable_detail, name='admin_consumable_detail'),
    path('edit-consumable_request/<int:request_id>/', views.admin_edit_consumable_request, name='admin_edit_consumable_request'),
    path('consumables/<int:request_id>/approve/', views.admin_request_approve, name='admin_request_approve'),
    path('consumables/<int:request_id>/reject/', views.admin_request_reject, name='admin_request_reject'),
    path('consumables/<int:request_id>/taking/', views.admin_request_taking, name='admin_request_taking'),
    path('add_payment/<int:request_id>/', views.add_payment, name='add_payment'),
    path('members_by_consumable_type/<int:id>/', views.members_by_consumable_type, name='members_by_consumable_type'),
    path('consumable_types_with_requests/',views.consumable_types_with_requests,name='consumable_types_with_requests'),
    path('add_single_consumable_payment/', views.add_single_consumable_payment, name='add_single_consumable_payment'),
    path('upload_consumable_payment/', views.upload_consumable_payment, name='upload_consumable_payment'),
]