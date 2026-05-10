"""
Day 4 / Week 2 — Teams Query Layer

All database access for the teams app lives here.
Views and services NEVER write raw queries — they call these functions.

This ensures:
  - select_related / prefetch_related used everywhere (no N+1)
  - Query logic is testable in isolation
  - Easy to swap DB backend later
"""

import logging
from django.db.models import Count, Q, Prefetch
from django.conf import settings

from teams.models import Team, Department, UserPosition, Repository, Contact, TeamActivity

logger = logging.getLogger('engie')


# ──────────────────────────────────────────────
# DEPARTMENT QUERIES
# ──────────────────────────────────────────────

def get_all_departments_with_teams():
    """
    Return all departments with prefetched active teams and team managers.
    Used on the Departments page and Organisation Chart.
    """
    return Department.objects.select_related('head_user').prefetch_related(
        Prefetch(
            'teams',
            queryset=Team.objects.select_related('manager').filter(
                status__in=[Team.Status.ACTIVE, Team.Status.RESTRUCTURING]
            ),
            to_attr='active_teams',
        )
    ).order_by('department_name')


def get_department_by_id(department_id):
    """Fetch a single department with head user and teams."""
    try:
        return Department.objects.select_related('head_user').prefetch_related(
            Prefetch('teams', queryset=Team.objects.select_related('manager'))
        ).get(pk=department_id)
    except Department.DoesNotExist:
        logger.warning(f'Department {department_id} not found')
        return None


def get_department_stats():
    """
    Return aggregated stats per department.
    Used in Reports and the Admin Dashboard.
    """
    return Department.objects.annotate(
        active_teams_count=Count('teams', filter=Q(teams__status=Team.Status.ACTIVE)),
        member_count=Count(
            'teams__members',
            filter=Q(
                teams__status=Team.Status.ACTIVE,
                teams__members__end_date__isnull=True,
            ),
            distinct=True,
        ),
        unmanaged_teams=Count(
            'teams',
            filter=Q(teams__manager__isnull=True, teams__status=Team.Status.ACTIVE),
        ),
    ).select_related('head_user').order_by('department_name')


# ──────────────────────────────────────────────
# TEAM QUERIES
# ──────────────────────────────────────────────

def get_all_teams_list():
    """
    Return all teams with manager and department for the Teams Directory.
    Optimized single query with all display data.
    """
    return (
        Team.objects.select_related('manager', 'department')
        .prefetch_related(
            Prefetch(
                'members',
                queryset=UserPosition.objects.filter(end_date__isnull=True).select_related('user'),
                to_attr='active_members',
            ),
            Prefetch(
                'contacts',
                queryset=Contact.objects.filter(is_primary=True),
                to_attr='primary_contacts',
            ),
        )
        .order_by('team_name')
    )


def get_team_detail(team_id):
    """
    Full team detail: manager, department, all members, repos, contacts.
    Used on the Team Detail page.
    """
    try:
        return (
            Team.objects.select_related('manager', 'department')
            .prefetch_related(
                Prefetch(
                    'members',
                    queryset=UserPosition.objects.filter(
                        end_date__isnull=True
                    ).select_related('user', 'reporting_to'),
                    to_attr='active_members',
                ),
                Prefetch(
                    'repositories',
                    queryset=Repository.objects.order_by('-is_main', 'repo_name'),
                ),
                Prefetch(
                    'contacts',
                    queryset=Contact.objects.order_by('-is_primary'),
                ),
            )
            .get(pk=team_id)
        )
    except Team.DoesNotExist:
        logger.warning(f'Team {team_id} not found')
        return None


def get_teams_without_managers():
    """Return all active teams with no assigned manager. Used in Reports."""
    return Team.objects.filter(
        manager__isnull=True,
        status=Team.Status.ACTIVE,
    ).select_related('department').order_by('department__department_name', 'team_name')


def get_teams_by_department(department_id):
    """All teams in a given department."""
    return Team.objects.filter(
        department_id=department_id
    ).select_related('manager', 'department').order_by('team_name')


def search_teams(query, department_id=None, manager_id=None, status=None):
    """
    Flexible team search.
    Matches on team_name, description, mission_purpose.
    Optional filters: department, manager, status.
    """
    qs = Team.objects.select_related('manager', 'department').prefetch_related(
        Prefetch('contacts', queryset=Contact.objects.filter(is_primary=True), to_attr='primary_contacts')
    )

    if query:
        qs = qs.filter(
            Q(team_name__icontains=query) |
            Q(description__icontains=query) |
            Q(mission_purpose__icontains=query) |
            Q(manager__full_name__icontains=query) |
            Q(manager__username__icontains=query) |
            Q(department__department_name__icontains=query)
        )

    if department_id:
        qs = qs.filter(department_id=department_id)

    if manager_id:
        qs = qs.filter(manager_id=manager_id)

    if status:
        qs = qs.filter(status=status)

    return qs.order_by('team_name')


def get_team_member_count(team_id):
    """Fast count of active members for a team."""
    return UserPosition.objects.filter(team_id=team_id, end_date__isnull=True).count()


def get_teams_with_member_counts():
    """
    Return all teams annotated with active member count.
    Used in constraint validation and risk engine.
    """
    return Team.objects.annotate(
        active_member_count=Count(
            'members',
            filter=Q(members__end_date__isnull=True),
        )
    ).select_related('manager', 'department').order_by('team_name')


# ──────────────────────────────────────────────
# ACTIVITY QUERIES
# ──────────────────────────────────────────────

def get_recent_activity(limit=20, team_id=None):
    """
    Fetch recent activity for the dashboard activity feed.
    If team_id is provided, scoped to that team.
    """
    qs = TeamActivity.objects.select_related('team', 'user').order_by('-created_at')
    if team_id:
        qs = qs.filter(team_id=team_id)
    return qs[:limit]


def get_global_dashboard_stats():
    """
    Aggregate stats for the Engineering Overview dashboard.
    Returns a dict with total teams, engineers, departments, dependencies.
    """
    from dependencies.models import TeamDependency

    total_teams = Team.objects.filter(status=Team.Status.ACTIVE).count()
    total_departments = Department.objects.filter(status=Department.Status.ACTIVE).count()
    total_engineers = UserPosition.objects.filter(end_date__isnull=True).values('user').distinct().count()
    total_dependencies = TeamDependency.objects.filter(status=TeamDependency.Status.ACTIVE).count()
    unmanaged_teams = Team.objects.filter(manager__isnull=True, status=Team.Status.ACTIVE).count()

    return {
        'total_teams': total_teams,
        'total_departments': total_departments,
        'total_engineers': total_engineers,
        'total_dependencies': total_dependencies,
        'unmanaged_teams': unmanaged_teams,
    }
