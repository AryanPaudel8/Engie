from django.contrib import admin
from teams.models import Department, Team, UserPosition, Repository, Contact, TeamActivity


class TeamInline(admin.TabularInline):
    model = Team
    extra = 0
    fields = ['team_name', 'manager', 'status']
    show_change_link = True


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['department_name', 'head_user', 'status', 'team_count_display']
    list_filter = ['status']
    search_fields = ['department_name']
    inlines = [TeamInline]

    def team_count_display(self, obj):
        return obj.teams.filter(status=Team.Status.ACTIVE).count()
    team_count_display.short_description = 'Active Teams'


class UserPositionInline(admin.TabularInline):
    model = UserPosition
    extra = 0
    fields = ['user', 'job_title', 'start_date', 'end_date', 'is_primary']


class ContactInline(admin.TabularInline):
    model = Contact
    extra = 0


class RepositoryInline(admin.TabularInline):
    model = Repository
    extra = 0


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ['team_name', 'department', 'manager', 'status', 'member_count_display', 'created_at']
    list_filter = ['status', 'department']
    search_fields = ['team_name', 'manager__full_name', 'department__department_name']
    inlines = [UserPositionInline, ContactInline, RepositoryInline]

    def member_count_display(self, obj):
        return obj.members.filter(end_date__isnull=True).count()
    member_count_display.short_description = 'Members'


@admin.register(TeamActivity)
class TeamActivityAdmin(admin.ModelAdmin):
    list_display = ['team', 'user', 'action_type', 'created_at']
    list_filter = ['action_type']
    search_fields = ['team__team_name', 'user__full_name']
    readonly_fields = ['created_at']
