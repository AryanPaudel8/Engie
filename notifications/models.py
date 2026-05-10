"""Notifications and AuditLog models for Engie."""
import logging
from django.db import models
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('engie')


class Notification(models.Model):
    class Type(models.TextChoices):
        INFO = 'info', 'Info'
        WARNING = 'warning', 'Warning'
        ALERT = 'alert', 'Alert'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.INFO)
    title = models.CharField(max_length=150)
    content = models.TextField(blank=True, default='')
    is_read = models.BooleanField(default=False)
    link = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'

    def __str__(self):
        return f'[{self.type}] {self.title} → {self.user}'


class AuditLog(models.Model):
    class Action(models.TextChoices):
        CREATE = 'create', 'Create'
        UPDATE = 'update', 'Update'
        DELETE = 'delete', 'Delete'
        LOGIN = 'login', 'Login'
        LOGOUT = 'logout', 'Logout'
        PASSWORD_RESET = 'password_reset', 'Password Reset'

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        related_name='audit_logs',
    )
    action = models.CharField(max_length=30, choices=Action.choices, db_index=True)
    entity_type = models.CharField(max_length=50, db_index=True)
    entity_id = models.CharField(max_length=50)
    entity_display = models.CharField(max_length=200, blank=True, default='')
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'

    def __str__(self):
        return f'[{self.action}] {self.entity_type}#{self.entity_id} by {self.actor}'
