from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.LandingPageView.as_view(), name='landing'),
    path('notification/<int:notification_id>/action/', views.handle_notification_action, name='handle_notification_action'),
    path('notification/<int:notification_id>/read/',   views.mark_notification_read,     name='mark_notification_read'),
    path('notification/<int:notification_id>/delete/', views.delete_notification,        name='delete_notification'),
]
