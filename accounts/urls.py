from django.urls import path
from . import views 

urlpatterns = [
    path('', views.login_view, name='login'),
    path('home/', views.home, name='home'),
    path('all_cases/', views.all_cases, name='all_cases'),
    path('upload_users/',views.upload_users, name='upload_users'),
    path('register/', views.user_registration, name='register'),
    path('logout', views.logout_view, name='logout'),
    path('complete_profile/', views.complete_profile, name='complete_profile'),
    path('all_members', views.all_members, name='all_members'),
    path('member_details/<int:id>/', views.member_detail, name='member_details'),
    path('delete_member/<int:id>/', views.delete_member, name='delete_member'),
    path('admin_member_detail/<int:id>/', views.admin_member_detail, name='admin_member_detail'),
    path('member_detail/<int:id>/', views.member_detail, name='member_detail'),
    path('deactivate_users', views.deactivate_users, name='deactivate_users'),
    path('activate_users', views.activate_users, name='activate_users'),

    path('reset_password_view/<int:id>/', views.reset_password_view, name='reset_password'),
    path('changePassword', views.changePassword, name='change_password'),
    path('add_user_to_group/<int:id>/', views.add_user_to_group, name='add_user_to_group'),

]
