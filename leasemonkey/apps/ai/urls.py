from django.urls import path
from . import views

app_name = 'ai'

urlpatterns = [
    path('send-message/', views.send_chat_message, name='send_chat_message'),
    path('admin/tickets/<int:ticket_id>/resolve/', views.resolve_ticket, name='resolve_ticket'),
]
