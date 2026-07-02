from django.contrib import admin
from .models import Land, Plot

class LandAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'area', 'average_plot_price', 'created_at')
    list_filter = ('owner', 'created_at')
    search_fields = ('name', 'owner__username', 'owner__email')

class PlotAdmin(admin.ModelAdmin):
    list_display = ('plot_number', 'land', 'area', 'price', 'facing', 'status')
    list_filter = ('land', 'status', 'facing')
    search_fields = ('plot_number', 'land__name')

admin.site.register(Land, LandAdmin)
admin.site.register(Plot, PlotAdmin)
