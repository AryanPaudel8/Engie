"""Dependencies API Views"""
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError
from dependencies.models import TeamDependency
from dependencies.serializers import TeamDependencySerializer
from dependencies import queries as dep_queries

logger = logging.getLogger('engie')


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def dependencies_view(request):
    """GET /api/dependencies/ | POST — create dependency (admin only)"""
    if request.method == 'GET':
        deps = dep_queries.get_all_active_dependencies()
        return Response(TeamDependencySerializer(deps, many=True).data)

    if not request.user.is_admin:
        return Response({'error': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)

    upstream_id = request.data.get('upstream_team_id')
    downstream_id = request.data.get('downstream_team_id')
    if not upstream_id or not downstream_id:
        return Response({'errors': {'detail': 'Both team IDs required.'}},
                        status=status.HTTP_400_BAD_REQUEST)

    try:
        dep = TeamDependency.objects.create(
            upstream_team_id=upstream_id,
            downstream_team_id=downstream_id,
            dependency_type=request.data.get('dependency_type', ''),
            description=request.data.get('description', ''),
            criticality=request.data.get('criticality', 'medium'),
        )
        dep.full_clean()
        return Response(TeamDependencySerializer(dep).data, status=status.HTTP_201_CREATED)
    except (ValidationError, Exception) as e:
        return Response({'errors': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def team_dependencies_view(request, team_id):
    """GET /api/teams/<id>/dependencies/ — upstream and downstream for a team"""
    upstream = dep_queries.get_upstream_dependencies(team_id)
    downstream = dep_queries.get_downstream_dependencies(team_id)
    return Response({
        'upstream': TeamDependencySerializer(upstream, many=True).data,
        'downstream': TeamDependencySerializer(downstream, many=True).data,
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def dependency_detail_view(request, dep_id):
    """DELETE /api/dependencies/<id>/"""
    if not request.user.is_admin:
        return Response({'error': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)
    try:
        dep = TeamDependency.objects.get(pk=dep_id)
        dep.delete()
        return Response({'message': 'Dependency removed.'})
    except TeamDependency.DoesNotExist:
        return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
