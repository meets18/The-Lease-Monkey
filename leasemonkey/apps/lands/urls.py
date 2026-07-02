from django.urls import path
from . import views

app_name = 'lands'

urlpatterns = [
    path('', views.lands_directory, name='directory'),
    path('plots/<slug:slug>/', views.plot_viewer, name='plot_viewer'),
    path('create/', views.create_land, name='create_land'),
    path('creator/', views.land_creator, name='land_creator'),
    path('creator/save/', views.save_land_layout, name='save_land_layout'),
    path('plots-creator/<slug:slug>/', views.plot_creator, name='plot_creator'),
    path('plots-creator/<slug:slug>/save/', views.save_plot_layout, name='save_plot_layout'),
    path('delete/<slug:slug>/', views.delete_land, name='delete_land'),
    path('plots-creator/<slug:slug>/delete/<str:plot_number>/', views.delete_plot, name='delete_plot'),
    path('plots-creator/<slug:slug>/update/<str:plot_number>/', views.update_plot, name='update_plot'),
]
