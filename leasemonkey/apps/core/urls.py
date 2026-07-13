from django.urls import path
from . import views
from . import google_auth_views

app_name = 'core'

urlpatterns = [
    path('', views.LandingPageView.as_view(), name='landing'),
    path('privacy/', views.PrivacyPolicyView.as_view(), name='privacy'),
    path('terms/', views.TermsOfServiceView.as_view(), name='terms'),
    path('notification/<int:notification_id>/action/', views.handle_notification_action, name='handle_notification_action'),
    path('notification/<int:notification_id>/read/',   views.mark_notification_read,     name='mark_notification_read'),
    path('notification/<int:notification_id>/delete/', views.delete_notification,        name='delete_notification'),

    # Contact form
    path('contact/submit/', views.submit_contact, name='submit_contact'),

    # One-time Google OAuth flow (admin only)
    path('google/authorize/',     google_auth_views.google_authorize,    name='google_authorize'),
    path('google/oauth2callback/', google_auth_views.google_oauth2callback, name='google_oauth2callback'),
]
