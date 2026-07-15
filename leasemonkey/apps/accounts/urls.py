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
    path('profile/', views.profile, name='profile'),
    path('profile/landowner/', views.landowner_profile, name='landowner_profile'),
    path('onboarding/landowner/', views.onboarding_landowner, name='onboarding_landowner'),
    path('preferences/', views.preferences, name='preferences'),
    path('profile/send-otp/', views.send_profile_otp, name='send_profile_otp'),
    path('profile/verify-otp/', views.verify_profile_otp, name='verify_profile_otp'),
    
    # Buyer Onboarding & Password Recovery URLs
    path('register/buyer/', views.buyer_register, name='buyer_register'),
    path('register/verify/', views.verify_email, name='verify_email'),
    path('register/onboarding-preferences/', views.onboarding_preferences, name='onboarding_preferences'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('forgot-password/reset/', views.forgot_password_reset, name='forgot_password_reset'),

    # Deletion Endpoints
    path('profile/send-delete-otp/', views.send_delete_otp, name='send_delete_otp'),
    path('profile/delete-account/', views.delete_account, name='delete_account'),
    path('admin/delete-buyer/<str:username>/', views.admin_delete_buyer, name='admin_delete_buyer'),
    path('admin/delete-landowner/<str:username>/', views.admin_delete_landowner, name='admin_delete_landowner'),

    # Landowner Registration Endpoints
    path('register/landowner/', views.landowner_register_step1, name='landowner_register_step1'),
    path('register/landowner/step2/', views.landowner_register_step2, name='landowner_register_step2'),
    path('register/landowner/step3/', views.landowner_register_step3, name='landowner_register_step3'),
    path('register/landowner/step4/', views.landowner_register_step4, name='landowner_register_step4'),
    path('register/landowner/send-otp/', views.landowner_register_send_otp, name='landowner_register_send_otp'),
    path('register/landowner/verify-otp/', views.landowner_register_verify_otp, name='landowner_register_verify_otp'),
    path('register/landowner/review/', views.landowner_register_review, name='landowner_register_review'),
    path('register/landowner/submit/', views.landowner_register_submit, name='landowner_register_submit'),
    path('register/landowner/success/', views.landowner_register_success, name='landowner_register_success'),

    # Admin Review Endpoints
    path('admin/landowner-applications/', views.admin_landowner_applications, name='admin_landowner_applications'),
    path('admin/landowner-applications/<int:app_id>/detail/', views.admin_landowner_application_detail, name='admin_landowner_application_detail'),
    path('admin/landowner-applications/<int:app_id>/approve/', views.admin_landowner_approve, name='admin_landowner_approve'),
    path('admin/landowner-applications/<int:app_id>/reject/', views.admin_landowner_reject, name='admin_landowner_reject'),
]
