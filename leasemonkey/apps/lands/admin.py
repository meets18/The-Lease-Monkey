from django.contrib import admin
from .models import Land, Plot, LandImage, Road, EntryExitPoint

class LandImageInline(admin.TabularInline):
    model = LandImage
    extra = 3

class LandAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'area', 'average_plot_price', 'created_at')
    list_filter = ('owner', 'created_at')
    search_fields = ('name', 'owner__username', 'owner__email')
    inlines = [LandImageInline]

class PlotAdmin(admin.ModelAdmin):
    list_display = ('plot_number', 'land', 'area', 'price', 'facing', 'status')
    list_filter = ('land', 'status', 'facing')
    search_fields = ('plot_number', 'land__name')

class RoadAdmin(admin.ModelAdmin):
    list_display = ('name', 'land', 'width_meters', 'created_at')
    list_filter = ('land', 'created_at')
    search_fields = ('name', 'land__name')

class EntryExitPointAdmin(admin.ModelAdmin):
    list_display = ('name', 'land', 'point_type', 'latitude', 'longitude', 'created_at')
    list_filter = ('land', 'point_type', 'created_at')
    search_fields = ('name', 'land__name')

admin.site.register(Land, LandAdmin)
admin.site.register(Plot, PlotAdmin)
admin.site.register(Road, RoadAdmin)
admin.site.register(EntryExitPoint, EntryExitPointAdmin)
