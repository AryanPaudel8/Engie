"""
Week 2 — Team & Department API Views

Clean, thin views. All logic in services/queries.
"""
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError

from teams import queries as team_queries
from teams import services as team_services
from teams.serializers import (
    TeamListSerializer, TeamDetailSerializer, DepartmentSerializer,
    TeamActivitySerializer,
)

logger = logging.getLogger('engie')


def _get_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR')


# ──────────────────────────────────────────────
# DASHBOARD
# ──────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats_view(request):
    """GET /api/dashboard/ — Engineering Overview stats"""
    stats = team_queries.get_global_dashboard_stats()
    activity = team_queries.get_recent_activity(limit=10)
    return Response({
        'stats': stats,
        'activity': TeamActivitySerializer(activity, many=True).data,
    })


# ──────────────────────────────────────────────
# TEAMS
# ──────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def teams_list_view(request):
    """
    GET  /api/teams/        — list all teams (with search/filter)
    POST /api/teams/        — create a new team (admin only)
    """
    if request.method == 'GET':
        query = request.GET.get('q', '')
        dept_id = request.GET.get('department')
        manager_id = request.GET.get('manager')
        team_status = request.GET.get('status')

        teams = team_queries.search_teams(query, department_id=dept_id,
                                          manager_id=manager_id, status=team_status)
        return Response({
            'results': TeamListSerializer(teams, many=True).data,
            'total': teams.count(),
        })

    # POST — admin only
    if not request.user.is_admin:
        return Response({'error': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        team = team_services.create_team(
            actor=request.user,
            department_id=request.data.get('department_id'),
            manager_id=request.data.get('manager_id'),
            team_name=request.data.get('team_name'),
            description=request.data.get('description', ''),
            mission_purpose=request.data.get('mission_purpose', ''),
            ip_address=_get_ip(request),
        )
        return Response(TeamDetailSerializer(team).data, status=status.HTTP_201_CREATED)
    except ValidationError as e:
        return Response({'errors': e.message_dict}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def team_detail_view(request, team_id):
    """
    GET    /api/teams/<id>/  — full team detail
    PATCH  /api/teams/<id>/  — update team (admin/manager)
    DELETE /api/teams/<id>/  — soft-delete team (admin only)
    """
    if request.method == 'GET':
        team = team_queries.get_team_detail(team_id)
        if not team:
            return Response({'error': 'Team not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(TeamDetailSerializer(team).data)

    if not request.user.is_admin:
        return Response({'error': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)

    if request.method == 'PATCH':
        try:
            team = team_services.update_team(
                actor=request.user, team_id=team_id,
                ip_address=_get_ip(request), **request.data
            )
            return Response(TeamDetailSerializer(team_queries.get_team_detail(team.pk)).data)
        except ValidationError as e:
            return Response({'errors': e.message_dict}, status=status.HTTP_400_BAD_REQUEST)

    if request.method == 'DELETE':
        try:
            team_services.delete_team(
                actor=request.user, team_id=team_id, ip_address=_get_ip(request)
            )
            return Response({'message': 'Team disbanded.'}, status=status.HTTP_200_OK)
        except ValidationError as e:
            return Response({'errors': e.message_dict}, status=status.HTTP_400_BAD_REQUEST)


# ──────────────────────────────────────────────
# DEPARTMENTS
# ──────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def departments_list_view(request):
    """GET /api/departments/ — all departments with teams"""
    departments = team_queries.get_all_departments_with_teams()
    return Response(DepartmentSerializer(departments, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def department_detail_view(request, dept_id):
    """GET /api/departments/<id>/"""
    dept = team_queries.get_department_by_id(dept_id)
    if not dept:
        return Response({'error': 'Department not found.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(DepartmentSerializer(dept).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def department_stats_view(request):
    """GET /api/departments/stats/ — for Reports page"""
    stats = team_queries.get_department_stats()
    return Response(DepartmentSerializer(stats, many=True).data)


# ──────────────────────────────────────────────
# REPORTS
# ──────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def reports_view(request):
    """GET /api/reports/ — dashboard reports (admin only)"""
    if not request.user.is_admin:
        return Response({'error': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)

    from dependencies.models import TeamDependency
    total_teams = team_queries.get_global_dashboard_stats()
    teams_no_mgr = team_queries.get_teams_without_managers()
    dept_stats = team_queries.get_department_stats()

    return Response({
        'summary': total_teams,
        'teams_without_managers': TeamListSerializer(teams_no_mgr, many=True).data,
        'department_summary': DepartmentSerializer(dept_stats, many=True).data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def users_list_view(request):
    """GET /api/users/ — list users for dropdowns (admin/manager)"""
    from users.models import UserAccount
    from users.serializers import UserSerializer
    users = UserAccount.objects.filter(is_active=True).order_by('full_name')
    return Response(UserSerializer(users, many=True).data)
