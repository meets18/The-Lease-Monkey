from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.portal_selection, name='portal_selection'),
    path('login/buyer/', views.buyer_login, name='buyer_login'),
    path('dashboard/buyer/', views.buyer_dashboard, name='buyer_dashboard'),
    path('logout/', views.logout_view, name='logout'),
]
