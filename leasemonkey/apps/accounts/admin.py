from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User

class UserAdmin(BaseUserAdmin):
    ordering = ('email',)
    list_display = ('email', 'role', 'status', 'is_verified', 'is_staff', 'is_superuser')
    list_filter = ('role', 'status', 'is_verified', 'is_staff', 'is_superuser')
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Role Details', {'fields': ('role', 'status', 'is_verified')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password', 'role', 'status', 'is_verified'),
        }),
    )
    
    search_fields = ('email', 'first_name', 'last_name')

admin.site.register(User, UserAdmin)
