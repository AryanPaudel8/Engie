from django.contrib import admin
from messaging.models import Message, MessageRecipient

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['sender', 'subject', 'status', 'created_at']
    list_filter = ['status']

@admin.register(MessageRecipient)
class MessageRecipientAdmin(admin.ModelAdmin):
    list_display = ['message', 'user', 'is_read', 'is_deleted']
