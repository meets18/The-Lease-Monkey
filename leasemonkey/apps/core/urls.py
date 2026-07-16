from django.urls import path
from . import views
from . import support_views
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

    # Support Ticket System (static routes before parameterized)
    path('support/',                           support_views.help_support,              name='help_support'),
    path('support/create-ticket/',             support_views.create_ticket_ajax,        name='create_ticket_ajax'),
    path('support/<str:ticket_id>/',           support_views.ticket_conversation,       name='ticket_conversation'),
    path('support/<str:ticket_id>/reply/',     support_views.reply_ticket_ajax,         name='reply_ticket_ajax'),
    path('support/<str:ticket_id>/update-status/', support_views.update_ticket_status_ajax, name='update_ticket_status_ajax'),
    path('support/<str:ticket_id>/detail/',    support_views.admin_ticket_detail_ajax,  name='admin_ticket_detail_ajax'),

    # One-time Google OAuth flow (admin only)
    path('google/authorize/',     google_auth_views.google_authorize,    name='google_authorize'),
    path('google/oauth2callback/', google_auth_views.google_oauth2callback, name='google_oauth2callback'),

    # Gated file serving (protected from public access)
    path('protected/<str:model_name>/<int:pk>/', views.serve_protected_file, name='serve_protected_file'),
]
