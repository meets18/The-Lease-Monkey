import os
from django.shortcuts import render
from .models import Land

def lands_directory(request):
    """Renders the catalog list of available land properties."""
    lands = Land.objects.all()
    return render(request, 'lands/directory.html', {'lands': lands})

def plot_viewer(request):
    """Renders the fullscreen Google Maps interactive plot viewer for the Sitapura site."""
    context = {
        'google_maps_api_key': os.getenv('GOOGLE_MAPS_API_KEY', '')
    }
    return render(request, 'lands/plot_viewer.html', context)
