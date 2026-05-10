"""
Dependencies Query Layer

Optimized fetching for dependency graph operations.
Used by the dependency intelligence service (DFS/BFS traversal).
"""
import logging
from django.db.models import Count, Q
from dependencies.models import TeamDependency

logger = logging.getLogger('engie')


def get_all_active_dependencies():
    """All active dependency edges with both teams prefetched."""
    return TeamDependency.objects.filter(
        status=TeamDependency.Status.ACTIVE
    ).select_related(
        'upstream_team__department',
        'downstream_team__department',
    ).order_by('-criticality')


def get_upstream_dependencies(team_id):
    """
    Teams that this team depends ON (what we need from others).
    e.g. Broadcast API depends on Platform Core → Platform Core is upstream.
    """
    return TeamDependency.objects.filter(
        downstream_team_id=team_id,
        status=TeamDependency.Status.ACTIVE,
    ).select_related('upstream_team__manager', 'upstream_team__department').order_by('-criticality')


def get_downstream_dependencies(team_id):
    """
    Teams that depend ON this team (who needs us).
    e.g. Platform Core is depended on by Broadcast API → Broadcast API is downstream.
    """
    return TeamDependency.objects.filter(
        upstream_team_id=team_id,
        status=TeamDependency.Status.ACTIVE,
    ).select_related('downstream_team__manager', 'downstream_team__department').order_by('-criticality')


def get_teams_with_dependency_counts():
    """
    All teams annotated with upstream/downstream dependency counts.
    Used by the Risk Engine to identify bottleneck teams.
    """
    from teams.models import Team
    return Team.objects.annotate(
        upstream_count=Count(
            'upstream_dependencies',
            filter=Q(upstream_dependencies__status=TeamDependency.Status.ACTIVE),
        ),
        downstream_count=Count(
            'downstream_dependencies',
            filter=Q(downstream_dependencies__status=TeamDependency.Status.ACTIVE),
        ),
    ).select_related('manager', 'department')


def get_dependency_graph_edges():
    """
    Return all active edges as lightweight dicts for graph traversal algorithms.
    Format: {upstream_team_id: [downstream_team_id, ...]}
    Used in DFS/BFS traversal in the intelligence service.
    """
    edges = TeamDependency.objects.filter(
        status=TeamDependency.Status.ACTIVE
    ).values('upstream_team_id', 'downstream_team_id', 'criticality')

    graph = {}
    for edge in edges:
        up = edge['upstream_team_id']
        down = edge['downstream_team_id']
        if up not in graph:
            graph[up] = []
        graph[up].append({'team_id': down, 'criticality': edge['criticality']})
    return graph


def check_dependency_exists(upstream_team_id, downstream_team_id):
    """Check if a specific dependency edge already exists."""
    return TeamDependency.objects.filter(
        upstream_team_id=upstream_team_id,
        downstream_team_id=downstream_team_id,
    ).exists()
