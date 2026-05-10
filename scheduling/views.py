"""
Day 14 — Scheduling Views
"""
import logging
from datetime import datetime
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError

from scheduling import services as sched_services
from scheduling.serializers import ScheduleEventSerializer

logger = logging.getLogger('engie')


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def events_view(request):
    """GET /api/events/ — user's events | POST — create event"""
    if request.method == 'GET':
        participations = sched_services.get_user_events(request.user)
        events = [p.event for p in participations]
        return Response(ScheduleEventSerializer(events, many=True).data)

    try:
        from django.utils.dateparse import parse_datetime
        event = sched_services.create_event(
            actor=request.user,
            team_id=request.data.get('team_id'),
            title=request.data.get('title', ''),
            start_datetime=parse_datetime(request.data.get('start_datetime', '')),
            end_datetime=parse_datetime(request.data.get('end_datetime', '')),
            event_type=request.data.get('event_type', 'meeting'),
            description=request.data.get('description', ''),
            platform=request.data.get('platform', ''),
            meeting_link=request.data.get('meeting_link', ''),
            participant_ids=request.data.get('participant_ids', []),
        )
        return Response(ScheduleEventSerializer(event).data, status=status.HTTP_201_CREATED)
    except (ValidationError, TypeError) as e:
        err = e.message_dict if hasattr(e, 'message_dict') else {'detail': str(e)}
        return Response({'errors': err}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def respond_to_invite_view(request, event_id):
    """POST /api/events/<id>/respond/"""
    try:
        sched_services.respond_to_invite(request.user, event_id, request.data.get('response'))
        return Response({'message': 'Response recorded.'})
    except ValidationError as e:
        return Response({'errors': e.message_dict}, status=status.HTTP_400_BAD_REQUEST)
