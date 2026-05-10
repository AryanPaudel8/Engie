"""Team Serializers"""
from rest_framework import serializers
from teams.models import Team, Department, UserPosition, Repository, Contact, TeamActivity


class DepartmentSerializer(serializers.ModelSerializer):
    head_name = serializers.CharField(source='head_user.full_name', read_only=True, default=None)
    team_count = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = ['id', 'department_name', 'description', 'status', 'email_distribution',
                  'head_name', 'team_count', 'created_at']

    def get_team_count(self, obj):
        return getattr(obj, 'team_count', obj.teams.filter(status=Team.Status.ACTIVE).count())


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ['id', 'contact_type', 'contact_value', 'is_primary']


class RepositorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Repository
        fields = ['id', 'repo_name', 'repo_type', 'url', 'is_main', 'description', 'last_commit_date']


class UserPositionSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = UserPosition
        fields = ['id', 'user_name', 'user_username', 'job_title', 'start_date', 'end_date', 'is_primary']


class TeamListSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.department_name', read_only=True)
    manager_name = serializers.CharField(source='manager.full_name', read_only=True, default=None)
    member_count = serializers.SerializerMethodField()
    upstream_count = serializers.SerializerMethodField()
    downstream_count = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = ['id', 'team_name', 'department_name', 'manager_name', 'status',
                  'member_count', 'upstream_count', 'downstream_count', 'created_at']

    def get_member_count(self, obj):
        return getattr(obj, 'member_count', 0)

    def get_upstream_count(self, obj):
        return obj.upstream_dependencies.filter(status='active').count()

    def get_downstream_count(self, obj):
        return obj.downstream_dependencies.filter(status='active').count()


class TeamDetailSerializer(serializers.ModelSerializer):
    department = DepartmentSerializer(read_only=True)
    manager = serializers.SerializerMethodField()
    members = UserPositionSerializer(source='active_members', many=True, read_only=True)
    repositories = RepositorySerializer(many=True, read_only=True)
    contacts = ContactSerializer(many=True, read_only=True)

    class Meta:
        model = Team
        fields = ['id', 'team_name', 'description', 'mission_purpose', 'status',
                  'department', 'manager', 'members', 'repositories', 'contacts', 'created_at']

    def get_manager(self, obj):
        if obj.manager:
            return {'id': obj.manager.pk, 'name': obj.manager.full_name,
                    'email': obj.manager.email, 'username': obj.manager.username}
        return None


class TeamActivitySerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    team_name = serializers.CharField(source='team.team_name', read_only=True)

    class Meta:
        model = TeamActivity
        fields = ['id', 'team_name', 'user_name', 'action_type', 'description', 'created_at']
