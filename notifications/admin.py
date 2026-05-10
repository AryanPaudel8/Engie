from django.contrib import admin
from notifications.models import Notification, AuditLog

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'type', 'title', 'is_read', 'created_at']
    list_filter = ['type', 'is_read']

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['actor', 'action', 'entity_type', 'entity_id', 'timestamp']
    list_filter = ['action', 'entity_type']
    readonly_fields = ['actor', 'action', 'entity_type', 'entity_id', 'old_values', 'new_values', 'ip_address', 'timestamp']
