from django.urls import path 
from .import views 


urlpatterns = [
    path('non_staff_member_dashboard/', views.non_staff_member_dashboard, name='non_staff_dashboard'),
    path('non_staff_members_list/', views.non_staff_members_list, name='non_staff_members_list'),
    path('non-member/<int:id>/savings/', views.non_staff_member_savings, name='non_staff_member_savings'),

]