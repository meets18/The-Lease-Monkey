from django.contrib import admin
from .models import Notification, Ticket, TicketReply


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display  = ('notif_type', 'title', 'recipient', 'sender', 'is_read', 'created_at')
    list_filter   = ('notif_type', 'is_read')
    search_fields = ('title', 'message', 'recipient__username', 'sender__username')
    readonly_fields = ('created_at',)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display  = ('ticket_id', 'subject', 'user', 'category', 'status', 'created_at')
    list_filter   = ('status', 'category')
    search_fields = ('ticket_id', 'subject', 'user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(TicketReply)
class TicketReplyAdmin(admin.ModelAdmin):
    list_display  = ('ticket', 'sender', 'created_at')
    list_filter   = ('created_at',)
    search_fields = ('ticket__ticket_id', 'sender__username', 'message')
