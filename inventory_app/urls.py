from django.urls import path
from . import views

urlpatterns = [
    path('inventory_home/', views.inventory_home, name='inventory_home'),
    path('register-supplier/', views.register_supplier, name='register_supplier'),
    path('receive-products/', views.receive_products_view, name='receive_products'),
    path('stock-return/', views.stock_return_view, name='stock_return'),
    path('product_list_view',views.product_list_view,name='product_list'),
    path('product_detail/<int:id>/',views.product_detail_view,name='product_detail'),
    
    path('plan/<int:id>/', views.create_selling_plan, name='create_selling_plan'),
    path('inventory-selling-plans/', views.selling_plan_list, name='inventory-selling-plans_list'),
    path('selling_plan_toggle_available/<int:pk>/toggle/', views.selling_plan_toggle_available, name='selling_plan_toggle_available'),
    path('receive_item_selling_plan_detail/<int:id>/', views.receive_item_selling_plan_detail, name='receive_item_selling_plan_detail'),
    path('inventory_selling_plan_edit/<int:pk>/', views.inventory_selling_plan_edit, name='inventory_selling_plan_edit'),
    path('inventory_plan_delete/<int:pk>/', views.inventory_plan_delete, name='inventory_plan_delete'),


    path('make_request/', views.member_make_request, name='member_make_request'),
    path('make-request-list/', views.member_make_request_list, name='member_make_request_list'),
    path('selling-plans/<int:pk>/toggle/', views.selling_plan_toggle_available, name='selling_plan_toggle_available'),
    path('guarantor-approval/<int:pk>/', views.guarantor_approval_view, name='guarantor_approval_view'),
    path('details/<int:id>/', views.make_request_details, name='make_request_details'),
    path('request/<int:request_id>/approve/', views.approve_member_request, name='approve_request'),
    path('request/<int:request_id>/decline/', views.decline_member_request, name='decline_request'),
    path('request/<int:request_id>/picked/', views.mark_item_picked, name='picked_request'),
    path("member-request/payment/add/",views.add_single_member_request_payment,name="add_single_member_request_payment",),
    path("upload_payments_excel/", views.upload_payments_excel, name="upload_payments_excel"),
    
    path('create/', views.create_member_request, name='create_member_request'),
    path('requests/', views.my_requests, name='my_requests'),
    path('requests/<int:pk>/', views.member_request_detail, name='member_request_detail'),
    path('items-report/', views.inventory_report, name='inventory_report'),
]