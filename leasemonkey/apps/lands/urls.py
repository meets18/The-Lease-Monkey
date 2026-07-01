from django.urls import path
from . import views

app_name = 'lands'

urlpatterns = [
    path('', views.lands_directory, name='directory'),
    path('plots/demo-land/', views.plot_viewer, name='plot_viewer'),
]
