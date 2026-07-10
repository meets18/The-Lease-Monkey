from django.urls import path
from . import views

app_name = 'lands'

urlpatterns = [
    path('', views.lands_directory, name='directory'),
    path('plots/<slug:slug>/', views.plot_viewer, name='plot_viewer'),
    path('create/', views.create_land, name='create_land'),
    path('creator/', views.land_creator, name='land_creator'),
    path('creator/discard/<slug:slug>/', views.discard_land_draft, name='discard_land_draft'),
    path('creator/save/', views.save_land_layout, name='save_land_layout'),
    path('plots-creator/<slug:slug>/', views.plot_creator, name='plot_creator'),
    path('plots-creator/<slug:slug>/save/', views.save_plot_layout, name='save_plot_layout'),
    path('delete/<slug:slug>/', views.delete_land, name='delete_land'),
    path('plots-creator/<slug:slug>/delete/<str:plot_number>/', views.delete_plot, name='delete_plot'),
    path('plots-creator/<slug:slug>/deallot/<str:plot_number>/', views.deallot_plot, name='deallot_plot'),
    path('plots-creator/<slug:slug>/update/<str:plot_number>/', views.update_plot, name='update_plot'),
    path('plots-creator/<slug:slug>/save-road/', views.save_road, name='save_road'),
    path('plots-creator/<slug:slug>/delete-road/<int:road_id>/', views.delete_road, name='delete_road'),
    path('plots-creator/<slug:slug>/save-gate/', views.save_gate, name='save_gate'),
    path('plots-creator/<slug:slug>/delete-gate/<int:gate_id>/', views.delete_gate, name='delete_gate'),
    path('plots/<slug:slug>/update-info/', views.update_land_info, name='update_land_info'),
    path('plots/<slug:slug>/add-photo/', views.add_gallery_photo, name='add_gallery_photo'),
    path('plots/<slug:slug>/delete-photo/<int:photo_id>/', views.delete_gallery_photo, name='delete_gallery_photo'),
    path('plots/<slug:slug>/update-photo-caption/<int:photo_id>/',   views.update_photo_caption,   name='update_photo_caption'),

    # ── Landowner Deletion Requests ───────────────────────────────────────────
    path('request-delete-land/<slug:slug>/',                         views.request_land_deletion,  name='request_land_deletion'),
    path('request-delete-plot/<slug:slug>/<str:plot_number>/',       views.request_plot_deletion,  name='request_plot_deletion'),

    # ── Purchase Requests ─────────────────────────────────────────────────────
    path('plots/<slug:slug>/request/<str:plot_number>/', views.purchase_request_form, name='purchase_request_form'),
    path('plots/<slug:slug>/request/<str:plot_number>/submit/', views.submit_purchase_request, name='submit_purchase_request'),
    path('purchase-request/send-otp/', views.send_otp, name='send_otp'),
    path('purchase-request/verify-otp/', views.verify_otp, name='verify_otp'),
    path('purchase-request/<int:request_id>/action/', views.purchase_request_action, name='purchase_request_action'),
    path('plots/<slug:slug>/toggle-save/<str:plot_number>/', views.toggle_saved_plot, name='toggle_saved_plot'),
]
