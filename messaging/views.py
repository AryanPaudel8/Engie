"""Messaging API Views"""
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from messaging.models import Message, MessageRecipient
from messaging.serializers import MessageSerializer
from users.models import UserAccount

logger = logging.getLogger('engie')


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def messages_view(request):
    """GET /api/messages/?folder=inbox|sent|drafts | POST — send/save message"""
    if request.method == 'GET':
        folder = request.GET.get('folder', 'inbox')
        if folder == 'sent':
            msgs = Message.objects.filter(sender=request.user, status='sent').select_related('sender')
        elif folder == 'drafts':
            msgs = Message.objects.filter(sender=request.user, status='draft').select_related('sender')
        else:  # inbox
            recipient_ids = MessageRecipient.objects.filter(
                user=request.user, is_deleted=False
            ).values_list('message_id', flat=True)
            msgs = Message.objects.filter(id__in=recipient_ids).select_related('sender')
        return Response(MessageSerializer(msgs[:50], many=True).data)

    # POST — compose
    subject = request.data.get('subject', '')
    content = request.data.get('message_content', '')
    msg_status = request.data.get('status', 'draft')
    recipient_ids = request.data.get('recipient_ids', [])
    parent_id = request.data.get('parent_message')

    if not content:
        return Response({'errors': {'message_content': ['Message body is required.']}},
                        status=status.HTTP_400_BAD_REQUEST)

    msg = Message.objects.create(
        sender=request.user,
        subject=subject,
        message_content=content,
        status=msg_status,
        parent_message_id=parent_id,
    )

    if msg_status == 'sent' and recipient_ids:
        for uid in recipient_ids:
            try:
                u = UserAccount.objects.get(pk=uid)
                MessageRecipient.objects.create(message=msg, user=u)
            except UserAccount.DoesNotExist:
                pass
    elif msg_status == 'sent' and not recipient_ids:
        # Reply — already has parent, create recipient for sender's other party
        pass

    return Response(MessageSerializer(msg).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def message_detail_view(request, msg_id):
    """GET /api/messages/<id>/"""
    try:
        msg = Message.objects.get(pk=msg_id)
        # Mark as read for current user
        MessageRecipient.objects.filter(message=msg, user=request.user).update(is_read=True)
        return Response(MessageSerializer(msg).data)
    except Message.DoesNotExist:
        return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unread_count_view(request):
    """GET /api/messages/unread-count/"""
    count = MessageRecipient.objects.filter(user=request.user, is_read=False, is_deleted=False).count()
    return Response({'unread': count})
