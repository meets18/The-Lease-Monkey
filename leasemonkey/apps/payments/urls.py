from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('create-cashfree-order/<slug:slug>/', views.create_cashfree_order, name='create_cashfree_order'),
    path('cashfree-return/', views.cashfree_return, name='cashfree_return'),
    path('cashfree-webhook/', views.cashfree_webhook, name='cashfree_webhook'),
    path('process-demo/<slug:slug>/', views.process_demo_payment, name='process_demo'),
]
