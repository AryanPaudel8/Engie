"""
Day 14 — Scheduling Services
"""
import logging
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from scheduling.models import ScheduleEvent, EventParticipant
from notifications.models import Notification

logger = logging.getLogger('engie')


@transaction.atomic
def create_event(actor, team_id, title, start_datetime, end_datetime,
                 event_type='meeting', description='', platform='',
                 meeting_link='', participant_ids=None, ip_address=None):
    """
    Create a scheduled event and notify all participants.
    Validates date/time constraints.
    """
    if not title or not title.strip():
        raise ValidationError({'title': 'Event title is required.'})

    if start_datetime >= end_datetime:
        raise ValidationError({'end_datetime': 'End time must be after start time.'})

    if start_datetime < timezone.now():
        raise ValidationError({'start_datetime': 'Event cannot be scheduled in the past.'})

    from teams.models import Team
    try:
        team = Team.objects.get(pk=team_id)
    except Team.DoesNotExist:
        raise ValidationError({'team': f'Team {team_id} not found.'})

    event = ScheduleEvent.objects.create(
        team=team,
        created_by=actor,
        title=title.strip(),
        description=description,
        event_type=event_type,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        platform=platform,
        meeting_link=meeting_link,
    )

    # Add creator as host
    EventParticipant.objects.create(
        event=event, user=actor, role=EventParticipant.Role.HOST,
        attendance_status=EventParticipant.AttendanceStatus.ACCEPTED,
    )

    # Add other participants
    participant_ids = participant_ids or []
    from users.models import UserAccount
    participants = UserAccount.objects.filter(pk__in=participant_ids, is_active=True).exclude(pk=actor.pk)
    for participant in participants:
        EventParticipant.objects.create(
            event=event,
            user=participant,
            role=EventParticipant.Role.ATTENDEE,
        )
        Notification.objects.create(
            user=participant,
            type=Notification.Type.INFO,
            title=f'Meeting invite: {title}',
            content=f'{actor.full_name} invited you to "{title}" at {start_datetime.strftime("%d %b %Y %H:%M")}',
            link=f'/schedule/{event.pk}/',
        )

    logger.info(f'Event "{title}" created by {actor} for team {team}')
    return event


def get_team_events(team_id, from_date=None, to_date=None):
    """Return events for a team, optionally filtered by date range."""
    qs = ScheduleEvent.objects.filter(team_id=team_id).prefetch_related(
        'participants__user'
    ).order_by('start_datetime')
    if from_date:
        qs = qs.filter(start_datetime__gte=from_date)
    if to_date:
        qs = qs.filter(start_datetime__lte=to_date)
    return qs


def get_user_events(user):
    """All events a user is participating in."""
    return EventParticipant.objects.filter(user=user).select_related(
        'event__team', 'event__created_by'
    ).order_by('event__start_datetime')


@transaction.atomic
def respond_to_invite(user, event_id, response):
    """
    User responds to an event invitation.
    response: 'accepted' | 'declined' | 'tentative'
    """
    valid_responses = {r.value for r in EventParticipant.AttendanceStatus}
    if response not in valid_responses:
        raise ValidationError({'response': f'Invalid response. Must be one of: {valid_responses}'})

    try:
        participation = EventParticipant.objects.get(event_id=event_id, user=user)
    except EventParticipant.DoesNotExist:
        raise ValidationError({'event': 'You are not a participant in this event.'})

    participation.attendance_status = response
    participation.save(update_fields=['attendance_status'])
    return participation
