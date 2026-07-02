from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.portal_selection, name='portal_selection'),
    path('login/buyer/', views.buyer_login, name='buyer_login'),
    path('login/landowner/', views.landowner_login, name='landowner_login'),
    path('login/admin/', views.admin_login, name='admin_login'),
    path('dashboard/buyer/', views.buyer_dashboard, name='buyer_dashboard'),
    path('dashboard/landowner/', views.landowner_dashboard, name='landowner_dashboard'),
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('logout/', views.logout_view, name='logout'),
]
