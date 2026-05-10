"""Messaging models for Engie internal messages."""
from django.db import models
from django.conf import settings
from django.utils import timezone


class Message(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SENT = 'sent', 'Sent'

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        related_name='sent_messages',
    )
    parent_message = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies',
    )
    subject = models.CharField(max_length=150, blank=True, default='')
    message_content = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Message'

    def __str__(self):
        return f'[{self.status}] {self.subject or "(no subject)"} from {self.sender}'


class MessageRecipient(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='recipients')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_messages')
    is_read = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        unique_together = [('message', 'user')]
        verbose_name = 'Message Recipient'

    def __str__(self):
        return f'{self.message} → {self.user}'
