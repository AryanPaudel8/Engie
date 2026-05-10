from rest_framework import serializers
from scheduling.models import ScheduleEvent, EventParticipant


class EventParticipantSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True)

    class Meta:
        model = EventParticipant
        fields = ['id', 'user_name', 'role', 'attendance_status', 'reminder_sent']


class ScheduleEventSerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source='team.team_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    participants = EventParticipantSerializer(many=True, read_only=True)

    class Meta:
        model = ScheduleEvent
        fields = [
            'id', 'team_name', 'created_by_name', 'title', 'description',
            'event_type', 'start_datetime', 'end_datetime', 'platform',
            'meeting_link', 'location', 'is_recurring', 'color',
            'participants', 'created_at',
        ]
