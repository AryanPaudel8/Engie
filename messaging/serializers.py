from rest_framework import serializers
from messaging.models import Message, MessageRecipient


class MessageRecipientSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    class Meta:
        model = MessageRecipient
        fields = ['id', 'user_id', 'user_name', 'user_username', 'is_read', 'is_deleted']


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.full_name', read_only=True)
    sender_username = serializers.CharField(source='sender.username', read_only=True)
    recipients = MessageRecipientSerializer(many=True, read_only=True)
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ['id', 'sender_name', 'sender_username', 'subject', 'message_content',
                  'status', 'parent_message', 'recipients', 'replies', 'created_at']

    def get_replies(self, obj):
        return MessageSerializer(obj.replies.all()[:5], many=True, context=self.context).data
