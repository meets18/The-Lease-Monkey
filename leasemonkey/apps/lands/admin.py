from django.contrib import admin
from .models import Land

class LandAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'area', 'average_plot_price', 'created_at')
    list_filter = ('owner', 'created_at')
    search_fields = ('name', 'owner__username', 'owner__email')

admin.site.register(Land, LandAdmin)
