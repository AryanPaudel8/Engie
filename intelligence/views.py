"""
intelligence/views.py
=====================
API endpoints for the Engie Intelligence Engine.

Endpoints:
  GET  /api/intelligence/risk/            — Organisational Risk Engine
  GET  /api/intelligence/impact/<id>/     — Impact Prediction for a team
  GET  /api/intelligence/circular/        — Circular Dependency Detection
  GET  /api/intelligence/chain/<id>/      — Dependency Chain BFS traversal
  GET  /api/intelligence/search/          — Deep Cognitive Search
  POST /api/intelligence/ask/             — Ask Engie (NL query)
  GET  /api/intelligence/contact/<id>/    — Smart Contact Routing
  GET  /api/intelligence/timeline/        — Organisation Timeline
  GET  /api/intelligence/constraints/     — Constraint Engine validation
  GET  /api/intelligence/incident/<id>/   — Incident Mode resolver
  GET  /api/intelligence/dashboard/       — Intelligence Dashboard (admin)
"""

import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from intelligence.services import (
    detect_organisational_risks,
    predict_impact,
    detect_circular_dependencies,
    get_dependency_chain,
    deep_search,
    ask_engie,
    get_smart_contact,
    get_organisation_timeline,
)
from teams.services import run_full_constraint_check

logger = logging.getLogger('engie')


# ─────────────────────────────────────────────────────────────────
# 1. RISK ENGINE
# ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def risk_view(request):
    """
    GET /api/intelligence/risk/

    Returns all detected organisational risks, ordered by severity.
    Accessible to all authenticated users (engineers need visibility too).
    """
    risks = detect_organisational_risks()
    return Response({
        'total': len(risks),
        'risks': [r.to_dict() for r in risks],
        'summary': {
            'critical': sum(1 for r in risks if r.severity == 'critical'),
            'high': sum(1 for r in risks if r.severity == 'high'),
            'medium': sum(1 for r in risks if r.severity == 'medium'),
            'low': sum(1 for r in risks if r.severity == 'low'),
        },
    })


# ─────────────────────────────────────────────────────────────────
# 2. IMPACT PREDICTION
# ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def impact_view(request, team_id):
    """
    GET /api/intelligence/impact/<team_id>/

    "If this team fails — what breaks?"
    Returns affected teams, impact level, and chain depth.
    """
    result = predict_impact(team_id)
    if 'error' in result:
        return Response(result, status=status.HTTP_404_NOT_FOUND)
    return Response(result)


# ─────────────────────────────────────────────────────────────────
# 3. CIRCULAR DEPENDENCY DETECTION
# ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def circular_view(request):
    """
    GET /api/intelligence/circular/

    Runs DFS over the full dependency graph and reports any cycles.
    """
    cycles = detect_circular_dependencies()
    return Response({
        'cycles_found': len(cycles),
        'healthy': len(cycles) == 0,
        'cycles': cycles,
    })


# ─────────────────────────────────────────────────────────────────
# 4. DEPENDENCY CHAIN
# ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def chain_view(request, team_id):
    """
    GET /api/intelligence/chain/<team_id>/?direction=downstream

    BFS chain traversal. direction = downstream (default) | upstream
    """
    direction = request.GET.get('direction', 'downstream')
    if direction not in ('upstream', 'downstream'):
        return Response({'error': 'direction must be "upstream" or "downstream"'},
                        status=status.HTTP_400_BAD_REQUEST)
    result = get_dependency_chain(team_id, direction=direction)
    if 'error' in result:
        return Response(result, status=status.HTTP_404_NOT_FOUND)
    return Response(result)


# ─────────────────────────────────────────────────────────────────
# 5. DEEP SEARCH
# ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_view(request):
    """
    GET /api/intelligence/search/?q=<query>

    Multi-entity cognitive search across teams, departments, users.
    """
    query = request.GET.get('q', '').strip()
    if not query:
        return Response({'error': 'Provide ?q= query parameter.'},
                        status=status.HTTP_400_BAD_REQUEST)
    result = deep_search(query)
    return Response(result)


# ─────────────────────────────────────────────────────────────────
# 6. ASK ENGIE
# ─────────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def ask_view(request):
    """
    POST /api/intelligence/ask/   { "query": "Who manages Platform Core?" }
    GET  /api/intelligence/ask/?q=Who manages Platform Core?

    Natural-language query interface to the Engie knowledge base.
    """
    if request.method == 'POST':
        query = request.data.get('query', '').strip()
    else:
        query = request.GET.get('q', '').strip()

    if not query:
        return Response({'error': 'Provide a query in body {"query": "..."} or ?q='},
                        status=status.HTTP_400_BAD_REQUEST)

    result = ask_engie(query)
    if 'error' in result and len(result) == 1:
        return Response(result, status=status.HTTP_400_BAD_REQUEST)
    return Response(result)


# ─────────────────────────────────────────────────────────────────
# 7. SMART CONTACT ROUTING
# ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def contact_view(request, team_id):
    """
    GET /api/intelligence/contact/<team_id>/

    "Who should I contact right now for this team?"
    Returns prioritised contact routing.
    """
    result = get_smart_contact(team_id)
    if 'error' in result:
        return Response(result, status=status.HTTP_404_NOT_FOUND)
    return Response(result)


# ─────────────────────────────────────────────────────────────────
# 8. ORGANISATION TIMELINE
# ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def timeline_view(request):
    """
    GET /api/intelligence/timeline/

    Chronological history of org events from AuditLog + TeamActivity.
    """
    limit = min(int(request.GET.get('limit', 50)), 200)
    entries = get_organisation_timeline(limit=limit)
    return Response({'total': len(entries), 'entries': entries})


# ─────────────────────────────────────────────────────────────────
# 9. CONSTRAINT ENGINE
# ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def constraints_view(request):
    """
    GET /api/intelligence/constraints/

    Runs the full system-wide constraint check.
    Returns warnings and violations for all teams and departments.
    Admin-only for full results; engineers see count only.
    """
    violations = run_full_constraint_check()
    dicts = [v.to_dict() for v in violations]
    if not request.user.is_admin:
        return Response({'total_violations': len(dicts), 'message': 'Contact admin for details.'})
    return Response({
        'total_violations': len(dicts),
        'healthy': len(dicts) == 0,
        'violations': dicts,
    })


# ─────────────────────────────────────────────────────────────────
# 10. INCIDENT MODE
# ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def incident_view(request, team_id):
    """
    GET /api/intelligence/incident/<team_id>/

    Incident Mode: given a failing team, return everything needed:
      - Who owns it (smart contact)
      - What it breaks (impact prediction)
      - Its dependency chain
      - Current risks for this team
    """
    from teams.models import Team
    from teams.queries import get_team_detail

    try:
        team = Team.objects.get(pk=team_id)
    except Team.DoesNotExist:
        return Response({'error': f'Team {team_id} not found.'}, status=status.HTTP_404_NOT_FOUND)

    contact = get_smart_contact(team_id)
    impact = predict_impact(team_id)
    chain_down = get_dependency_chain(team_id, direction='downstream')
    chain_up = get_dependency_chain(team_id, direction='upstream')

    # Risks specific to this team
    all_risks = detect_organisational_risks()
    team_risks = [r.to_dict() for r in all_risks if r.team_id == team_id]

    logger.info('[IncidentMode] Incident resolved for team_id=%s', team_id)

    return Response({
        'team_id': team_id,
        'team_name': team.team_name,
        'status': team.status,
        'owner': contact,
        'impact': impact,
        'downstream_chain': chain_down,
        'upstream_chain': chain_up,
        'risks': team_risks,
        'incident_summary': (
            f'Team "{team.team_name}" failure would affect '
            f'{impact.get("affected_count", 0)} downstream team(s) '
            f'at impact level {impact.get("impact_level", "UNKNOWN")}. '
            f'Contact: {contact.get("recommended", {}).get("name", "unknown")}.'
        ),
    })


# ─────────────────────────────────────────────────────────────────
# 11. INTELLIGENCE DASHBOARD (ADMIN)
# ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def intelligence_dashboard_view(request):
    """
    GET /api/intelligence/dashboard/

    System-thinking admin dashboard:
      - Total/risky/critical/isolated team counts
      - Most depended-on teams
      - Circular dependency status
      - Constraint violations summary
    """
    from teams.models import Team
    from dependencies.models import TeamDependency
    from collections import Counter

    # Risk summary
    risks = detect_organisational_risks()
    risk_summary = {
        'total': len(risks),
        'critical': sum(1 for r in risks if r.severity == 'critical'),
        'high': sum(1 for r in risks if r.severity == 'high'),
        'medium': sum(1 for r in risks if r.severity == 'medium'),
        'low': sum(1 for r in risks if r.severity == 'low'),
    }

    # Most depended-on teams
    dep_counts = Counter()
    for dep in TeamDependency.objects.filter(status='active').values('upstream_team_id'):
        dep_counts[dep['upstream_team_id']] += 1

    top_depended = []
    for team_id, count in dep_counts.most_common(5):
        try:
            t = Team.objects.get(pk=team_id)
            top_depended.append({'team_name': t.team_name, 'dependents': count, 'team_id': team_id})
        except Team.DoesNotExist:
            pass

    # Circular check
    cycles = detect_circular_dependencies()

    # Constraints
    violations = run_full_constraint_check()

    # Counts
    active_count = Team.objects.filter(status='active').count()
    risky_count = len({r.team_id for r in risks if r.severity in ('critical', 'high')})
    isolated_count = len([r for r in risks if r.risk_type == 'ISOLATED'])

    return Response({
        'team_health': {
            'active_teams': active_count,
            'risky_teams': risky_count,
            'isolated_teams': isolated_count,
            'circular_dependencies': len(cycles),
        },
        'risk_summary': risk_summary,
        'top_depended_on': top_depended,
        'constraint_violations': len(violations),
        'system_healthy': (
            len(cycles) == 0 and len(violations) == 0 and risk_summary['critical'] == 0
        ),
    })
