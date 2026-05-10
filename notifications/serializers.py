from rest_framework import serializers
from notifications.models import Notification, AuditLog

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'type', 'title', 'content', 'is_read', 'link', 'created_at']

class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.full_name', read_only=True)
    class Meta:
        model = AuditLog
        fields = ['id', 'actor_name', 'action', 'entity_type', 'entity_id', 'entity_display',
                  'old_values', 'new_values', 'ip_address', 'timestamp']
