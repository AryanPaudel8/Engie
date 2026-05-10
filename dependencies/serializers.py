from rest_framework import serializers
from dependencies.models import TeamDependency


class TeamDependencySerializer(serializers.ModelSerializer):
    upstream_team_name = serializers.CharField(source='upstream_team.team_name', read_only=True)
    downstream_team_name = serializers.CharField(source='downstream_team.team_name', read_only=True)

    class Meta:
        model = TeamDependency
        fields = [
            'id', 'upstream_team', 'upstream_team_name',
            'downstream_team', 'downstream_team_name',
            'dependency_type', 'criticality', 'status', 'description',
            'created_at', 'last_verified',
        ]
        read_only_fields = ['id', 'created_at']
