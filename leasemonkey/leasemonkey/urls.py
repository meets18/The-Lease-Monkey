"""
URL configuration for leasemonkey project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.lands.views import plot_viewer_vanity

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('apps.accounts.urls')),
    path('lands/', include('apps.lands.urls')),
    path('ai/', include('apps.ai.urls')),
    path('', include('apps.core.urls', namespace='core')),
    path("__reload__/", include("django_browser_reload.urls")),
    # Vanity URL: /<owner_username>/<land_slug>/ → plot viewer
    # Must be last to avoid shadowing other routes
    path('<str:owner_username>/<slug:slug>/', plot_viewer_vanity, name='plot_viewer_vanity'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
