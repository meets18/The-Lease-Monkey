from django.shortcuts import render
from .models import Land

def lands_directory(request):
    """Renders the catalog list of available land properties."""
    lands = Land.objects.all()
    return render(request, 'lands/directory.html', {'lands': lands})
