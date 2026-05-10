"""
Day 5 — Scheduling Models: ScheduleEvent, EventParticipant
"""
import logging
from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('engie')


class ScheduleEvent(models.Model):
    class EventType(models.TextChoices):
        MEETING = 'meeting', 'Meeting'
        DEADLINE = 'deadline', 'Deadline'
        REVIEW = 'review', 'Review'

    team = models.ForeignKey('teams.Team', on_delete=models.CASCADE, related_name='events')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        related_name='created_events',
    )
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True, default='')
    event_type = models.CharField(max_length=20, choices=EventType.choices, default=EventType.MEETING)
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    platform = models.CharField(max_length=50, blank=True, default='')
    meeting_link = models.URLField(max_length=255, blank=True, default='')
    location = models.CharField(max_length=150, blank=True, default='')
    is_recurring = models.BooleanField(default=False)
    recurrence_rule = models.CharField(max_length=100, blank=True, default='')
    color = models.CharField(max_length=20, default='#4A90D9')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = 'Schedule Event'
        ordering = ['start_datetime']
        indexes = [models.Index(fields=['team', 'start_datetime'])]

    def __str__(self):
        return f'{self.title} ({self.team}) @ {self.start_datetime}'

    def clean(self):
        if self.end_datetime and self.start_datetime:
            if self.end_datetime < self.start_datetime:
                raise ValidationError({'end_datetime': 'End datetime must be after start datetime.'})
        if self.is_recurring and not self.recurrence_rule:
            raise ValidationError({'recurrence_rule': 'Recurring events must have a recurrence rule.'})


class EventParticipant(models.Model):
    class Role(models.TextChoices):
        HOST = 'host', 'Host'
        ATTENDEE = 'attendee', 'Attendee'

    class AttendanceStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        DECLINED = 'declined', 'Declined'
        TENTATIVE = 'tentative', 'Tentative'

    event = models.ForeignKey(ScheduleEvent, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='event_participations',
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.ATTENDEE)
    attendance_status = models.CharField(max_length=20, choices=AttendanceStatus.choices, default=AttendanceStatus.PENDING)
    reminder_sent = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Event Participant'
        unique_together = [('event', 'user')]

    def __str__(self):
        return f'{self.user} @ {self.event} [{self.role}]'
