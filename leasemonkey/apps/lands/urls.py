from django.urls import path
from . import views

app_name = 'lands'

urlpatterns = [
    path('', views.lands_directory, name='directory'),
]
