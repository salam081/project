from django.urls import path
from . import views

urlpatterns = [
    path('inventory_home/', views.inventory_home, name='inventory_home'),
    path('receive-products/', views.receive_products_view, name='receive_products'),
    path('stock-return/', views.stock_return_view, name='stock_return'),
    path('product_list_view',views.product_list_view,name='product_list'),
    path('product_detail/<int:id>/',views.product_detail_view,name='product_detail'),
    
    path('plan/<int:id>/', views.create_selling_plan, name='create_selling_plan'),
    path('receive_plan_detail/<int:id>/', views.receive_item_selling_plan_detail, name='receive_item_selling_plan_detail'),
    
    
    path('make_request/', views.member_make_request, name='member_make_request'),
    path('details/<int:id>/', views.make_request_details, name='make_request_details'),
    path('request/<int:request_id>/approve/', views.approve_member_request, name='approve_request'),
    path('request/<int:request_id>/decline/', views.decline_member_request, name='decline_request'),
    path('request/<int:request_id>/picked/', views.mark_item_picked, name='picked_request'),
    path("upload_payments_excel/", views.upload_payments_excel, name="upload_payments_excel"),
    
    path('create/', views.create_member_request, name='create_member_request'),
    path('requests/', views.my_requests, name='my_requests'),
    path('requests/<int:pk>/', views.member_request_detail, name='member_request_detail'),
]