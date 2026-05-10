"""Notifications API Views"""
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from notifications.models import Notification, AuditLog
from notifications.serializers import NotificationSerializer, AuditLogSerializer

logger = logging.getLogger('engie')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notifications_view(request):
    """GET /api/notifications/ — user's notifications"""
    notifs = Notification.objects.filter(user=request.user)[:50]
    return Response(NotificationSerializer(notifs, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notification_read_view(request, notif_id):
    """POST /api/notifications/<id>/read/"""
    try:
        n = Notification.objects.get(pk=notif_id, user=request.user)
        n.is_read = True
        n.save(update_fields=['is_read'])
        return Response({'message': 'Marked as read.'})
    except Notification.DoesNotExist:
        return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_read_view(request):
    """POST /api/notifications/read-all/"""
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return Response({'message': 'All notifications marked as read.'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def audit_log_view(request):
    """GET /api/audit/ — admin only"""
    if not request.user.is_admin:
        return Response({'error': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)
    logs = AuditLog.objects.select_related('actor').order_by('-timestamp')[:200]
    return Response(AuditLogSerializer(logs, many=True).data)
