"""
intelligence/services.py
========================
Engie Intelligence Engine — Day 15-21 feature layer.

Implements:
  1. detect_organisational_risks()   — Risk Engine (NO_MANAGER, BOTTLENECK, ISOLATED, SPOF)
  2. predict_impact()                — Impact Prediction Engine (BFS downstream traversal)
  3. detect_circular_dependencies()  — DFS cycle detection
  4. get_dependency_chain()          — BFS chain traversal (upstream or downstream)
  5. deep_search()                   — Cognitive multi-entity search
  6. ask_engie()                     — Natural-language query resolver
  7. get_smart_contact()             — Smart Contact Routing
  8. get_organisation_timeline()     — Org Timeline from AuditLog + TeamActivity

All functions follow the Service Layer pattern:
  Views → Intelligence Services → Query Layer → Models → Response

No Django ORM queries appear in views. All logic lives here.
"""

from __future__ import annotations

import logging
import re
from collections import deque, defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger('engie')


# ─────────────────────────────────────────────────────────────────
# RESULT DATA CLASSES
# ─────────────────────────────────────────────────────────────────

@dataclass
class RiskResult:
    """A single detected organisational risk."""
    risk_type: str          # NO_MANAGER | BOTTLENECK | ISOLATED | SINGLE_POINT_OF_FAILURE | UNDERSTAFFED
    severity: str           # critical | high | medium | low
    team_id: int
    team_name: str
    message: str
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            'risk_type': self.risk_type,
            'severity': self.severity,
            'team_id': self.team_id,
            'team_name': self.team_name,
            'message': self.message,
            'detail': self.detail,
        }


# ─────────────────────────────────────────────────────────────────
# 1. RISK ENGINE
# ─────────────────────────────────────────────────────────────────

def detect_organisational_risks() -> list[RiskResult]:
    """
    Scan the entire organisation for structural problems.

    Checks (in order of severity):
      - SINGLE_POINT_OF_FAILURE  : team depended on by ≥ 5 others
      - BOTTLENECK               : team depended on by ≥ 3 others
      - NO_MANAGER               : active team has no manager assigned
      - UNDERSTAFFED             : team has fewer than ENGIE_MIN_ENGINEERS_PER_TEAM members
      - ISOLATED                 : active team has zero dependencies in either direction

    Returns a list of RiskResult, ordered by severity (critical first).
    """
    from teams.models import Team
    from dependencies.models import TeamDependency

    SEVERITY_ORDER = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
    risks: list[RiskResult] = []

    # Count downstream dependents per team (how many teams rely ON each team)
    downstream_counts: dict[int, int] = defaultdict(int)
    upstream_counts: dict[int, int] = defaultdict(int)
    for dep in TeamDependency.objects.filter(status='active').values('upstream_team_id', 'downstream_team_id'):
        downstream_counts[dep['upstream_team_id']] += 1
        upstream_counts[dep['downstream_team_id']] += 1

    active_teams = Team.objects.filter(
        status__in=[Team.Status.ACTIVE, Team.Status.RESTRUCTURING]
    ).prefetch_related('members')

    active_team_ids = set()
    for team in active_teams:
        active_team_ids.add(team.pk)
        member_count = team.members.filter(end_date__isnull=True).count()
        dep_downstream = downstream_counts.get(team.pk, 0)
        dep_upstream = upstream_counts.get(team.pk, 0)

        # ── SINGLE POINT OF FAILURE ─────────────────────────────
        if dep_downstream >= 5:
            risks.append(RiskResult(
                risk_type='SINGLE_POINT_OF_FAILURE',
                severity='critical',
                team_id=team.pk,
                team_name=team.team_name,
                message=f'"{team.team_name}" is a single point of failure — {dep_downstream} teams depend on it.',
                detail={'dependent_teams': dep_downstream},
            ))
        # ── BOTTLENECK ──────────────────────────────────────────
        elif dep_downstream >= 3:
            risks.append(RiskResult(
                risk_type='BOTTLENECK',
                severity='high',
                team_id=team.pk,
                team_name=team.team_name,
                message=f'"{team.team_name}" is a dependency bottleneck — {dep_downstream} teams rely on it.',
                detail={'dependent_teams': dep_downstream},
            ))

        # ── NO MANAGER ──────────────────────────────────────────
        if team.manager_id is None:
            risks.append(RiskResult(
                risk_type='NO_MANAGER',
                severity='high',
                team_id=team.pk,
                team_name=team.team_name,
                message=f'"{team.team_name}" has no manager assigned.',
                detail={},
            ))

        # ── UNDERSTAFFED ────────────────────────────────────────
        if member_count < 1:
            risks.append(RiskResult(
                risk_type='UNDERSTAFFED',
                severity='medium',
                team_id=team.pk,
                team_name=team.team_name,
                message=f'"{team.team_name}" has {member_count} active member(s) — team appears empty.',
                detail={'member_count': member_count},
            ))

        # ── ISOLATED ────────────────────────────────────────────
        if dep_downstream == 0 and dep_upstream == 0:
            risks.append(RiskResult(
                risk_type='ISOLATED',
                severity='low',
                team_id=team.pk,
                team_name=team.team_name,
                message=f'"{team.team_name}" is isolated — no upstream or downstream dependencies.',
                detail={},
            ))

    risks.sort(key=lambda r: SEVERITY_ORDER.get(r.severity, 9))
    logger.info('[RiskEngine] %d risks detected across %d active teams.', len(risks), len(active_team_ids))
    return risks


# ─────────────────────────────────────────────────────────────────
# 2. IMPACT PREDICTION ENGINE
# ─────────────────────────────────────────────────────────────────

def predict_impact(team_id: int) -> dict[str, Any]:
    """
    "If this team fails — what breaks?"

    Performs a BFS over downstream dependencies starting from `team_id`.
    Returns:
      - impact_level    : LOW | MEDIUM | HIGH | CRITICAL
      - affected_count  : number of transitively affected teams
      - affected_teams  : list of team names
      - depth           : longest chain length
    """
    from dependencies.models import TeamDependency
    from teams.models import Team

    try:
        root = Team.objects.get(pk=team_id)
    except Team.DoesNotExist:
        return {'error': f'Team {team_id} not found.'}

    # Build adjacency: upstream_id → list of downstream_ids
    adjacency: dict[int, list[int]] = defaultdict(list)
    id_to_name: dict[int, str] = {}
    for dep in TeamDependency.objects.filter(status='active').select_related('downstream_team'):
        adjacency[dep.upstream_team_id].append(dep.downstream_team_id)
        id_to_name[dep.downstream_team_id] = dep.downstream_team.team_name
        id_to_name[dep.upstream_team_id] = dep.upstream_team.team_name

    # BFS
    visited: set[int] = set()
    queue: deque[tuple[int, int]] = deque([(team_id, 0)])
    max_depth = 0

    while queue:
        current_id, depth = queue.popleft()
        for neighbour_id in adjacency.get(current_id, []):
            if neighbour_id not in visited and neighbour_id != team_id:
                visited.add(neighbour_id)
                max_depth = max(max_depth, depth + 1)
                queue.append((neighbour_id, depth + 1))

    count = len(visited)
    if count == 0:
        level = 'LOW'
    elif count <= 2:
        level = 'MEDIUM'
    elif count <= 5:
        level = 'HIGH'
    else:
        level = 'CRITICAL'

    affected_names = [id_to_name.get(tid, f'Team#{tid}') for tid in visited]

    logger.info('[ImpactPrediction] team_id=%s impact=%s affected=%d depth=%d',
                team_id, level, count, max_depth)

    return {
        'team_id': team_id,
        'team_name': root.team_name,
        'impact_level': level,
        'affected_count': count,
        'affected_teams': affected_names,
        'chain_depth': max_depth,
    }


# ─────────────────────────────────────────────────────────────────
# 3. CIRCULAR DEPENDENCY DETECTION (DFS)
# ─────────────────────────────────────────────────────────────────

def detect_circular_dependencies() -> list[dict]:
    """
    DFS-based cycle detection across the full dependency graph.

    Returns a list of cycles, each as:
      {'cycle': ['Team A', 'Team B', 'Team A'], 'length': 2}
    """
    from dependencies.models import TeamDependency

    # Build adjacency: upstream → downstream
    adjacency: dict[int, list[int]] = defaultdict(list)
    id_to_name: dict[int, str] = {}

    for dep in TeamDependency.objects.filter(status='active').select_related(
        'upstream_team', 'downstream_team'
    ):
        adjacency[dep.upstream_team_id].append(dep.downstream_team_id)
        id_to_name[dep.upstream_team_id] = dep.upstream_team.team_name
        id_to_name[dep.downstream_team_id] = dep.downstream_team.team_name

    visited: set[int] = set()
    rec_stack: set[int] = set()
    cycles: list[dict] = []
    path: list[int] = []

    def dfs(node: int) -> None:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbour in adjacency.get(node, []):
            if neighbour not in visited:
                dfs(neighbour)
            elif neighbour in rec_stack:
                # Found a cycle — extract it
                cycle_start = path.index(neighbour)
                cycle_ids = path[cycle_start:] + [neighbour]
                cycle_names = [id_to_name.get(i, f'Team#{i}') for i in cycle_ids]
                cycles.append({
                    'cycle': cycle_names,
                    'length': len(cycle_ids) - 1,
                    'team_ids': cycle_ids,
                })

        path.pop()
        rec_stack.discard(node)

    all_nodes = set(adjacency.keys())
    for n in list(adjacency.values()):
        all_nodes.update(n)

    for node in all_nodes:
        if node not in visited:
            dfs(node)

    logger.info('[CircularDetection] %d cycle(s) found.', len(cycles))
    return cycles


# ─────────────────────────────────────────────────────────────────
# 4. DEPENDENCY CHAIN TRAVERSAL (BFS)
# ─────────────────────────────────────────────────────────────────

def get_dependency_chain(team_id: int, direction: str = 'downstream') -> dict[str, Any]:
    """
    BFS traversal of the dependency graph from a given team.

    direction: 'downstream' — teams that would be affected if this team fails
               'upstream'   — teams this team relies upon

    Returns:
      - chain         : list of team names in traversal order
      - total_affected: count
      - depth         : max hop depth
      - critical_path : longest single path
    """
    from dependencies.models import TeamDependency
    from teams.models import Team

    try:
        root = Team.objects.get(pk=team_id)
    except Team.DoesNotExist:
        return {'error': f'Team {team_id} not found.'}

    adjacency: dict[int, list[int]] = defaultdict(list)
    id_to_name: dict[int, str] = {team_id: root.team_name}

    deps = TeamDependency.objects.filter(status='active').select_related(
        'upstream_team', 'downstream_team'
    )
    for dep in deps:
        if direction == 'downstream':
            adjacency[dep.upstream_team_id].append(dep.downstream_team_id)
        else:
            adjacency[dep.downstream_team_id].append(dep.upstream_team_id)
        id_to_name[dep.upstream_team_id] = dep.upstream_team.team_name
        id_to_name[dep.downstream_team_id] = dep.downstream_team.team_name

    visited: list[str] = []
    seen: set[int] = {team_id}
    queue: deque[tuple[int, int, list]] = deque([(team_id, 0, [root.team_name])])
    max_depth = 0
    critical_path: list[str] = []

    while queue:
        current_id, depth, path = queue.popleft()
        children = adjacency.get(current_id, [])

        if not children and depth > max_depth:
            max_depth = depth
            critical_path = path

        for neighbour_id in children:
            if neighbour_id not in seen:
                seen.add(neighbour_id)
                name = id_to_name.get(neighbour_id, f'Team#{neighbour_id}')
                visited.append(name)
                new_path = path + [name]
                if depth + 1 > max_depth:
                    max_depth = depth + 1
                    critical_path = new_path
                queue.append((neighbour_id, depth + 1, new_path))

    return {
        'team_id': team_id,
        'team_name': root.team_name,
        'direction': direction,
        'chain': visited,
        'total_affected': len(visited),
        'depth': max_depth,
        'critical_path': critical_path,
    }


# ─────────────────────────────────────────────────────────────────
# 5. DEEP SEARCH (COGNITIVE SEARCH)
# ─────────────────────────────────────────────────────────────────

def deep_search(query: str) -> dict[str, Any]:
    """
    Multi-entity cognitive search. Understands:
      - partial names (e.g. 'broad' → 'Broadcast API')
      - role queries (e.g. 'backend team auth')
      - person queries (e.g. 'patel')

    Returns ranked results across teams, departments, and users.
    """
    from teams.models import Team, Department
    from users.models import UserAccount

    query = (query or '').strip()
    if len(query) < 2:
        return {'results': [], 'total': 0, 'message': 'Query too short — minimum 2 characters.'}

    terms = [t.lower() for t in query.split()]
    results: list[dict] = []

    # ── TEAMS ────────────────────────────────────────────────────
    for team in Team.objects.select_related('manager', 'department').all():
        score = 0
        text = f"{team.team_name} {team.description or ''} {team.mission_purpose or ''}".lower()
        for term in terms:
            if term in team.team_name.lower():
                score += 10
            elif term in text:
                score += 3
        if score > 0:
            results.append({
                'type': 'team',
                'id': team.pk,
                'name': team.team_name,
                'subtitle': f'{team.department.department_name if team.department else ""} · {team.status}',
                'manager': team.manager.full_name if team.manager else None,
                'score': score,
            })

    # ── DEPARTMENTS ──────────────────────────────────────────────
    for dept in Department.objects.select_related('head_user').all():
        score = 0
        text = f"{dept.department_name} {dept.description or ''}".lower()
        for term in terms:
            if term in dept.department_name.lower():
                score += 10
            elif term in text:
                score += 3
        if score > 0:
            results.append({
                'type': 'department',
                'id': dept.pk,
                'name': dept.department_name,
                'subtitle': f'Head: {dept.head_user.full_name if dept.head_user else "unassigned"}',
                'score': score,
            })

    # ── USERS ────────────────────────────────────────────────────
    for user in UserAccount.objects.filter(is_active=True):
        score = 0
        text = f"{user.full_name} {user.username} {user.email}".lower()
        for term in terms:
            if term in user.full_name.lower():
                score += 8
            elif term in text:
                score += 2
        if score > 0:
            results.append({
                'type': 'user',
                'id': user.pk,
                'name': user.full_name,
                'subtitle': f'@{user.username} · {user.role}',
                'score': score,
            })

    results.sort(key=lambda r: r['score'], reverse=True)
    top = results[:20]

    logger.info('[DeepSearch] query="%s" → %d results', query, len(top))
    return {'results': top, 'total': len(top), 'query': query}


# ─────────────────────────────────────────────────────────────────
# 6. ASK ENGIE — NATURAL LANGUAGE QUERY RESOLVER
# ─────────────────────────────────────────────────────────────────

# Intent patterns: regex → intent key
_INTENT_PATTERNS = [
    (re.compile(r'\b(who (manages?|owns?|leads?|runs?|is (the )?manager))\b', re.I), 'owner'),
    (re.compile(r'\b(depends? on|upstream|what does .+ need)\b', re.I), 'upstream'),
    (re.compile(r'\b(depends? on .+|downstream|what relies? on|what breaks if)\b', re.I), 'impact'),
    (re.compile(r'\b(critical|single point|bottleneck|spof|risky)\b', re.I), 'risk'),
    (re.compile(r'\b(without manager|unmanaged|no manager)\b', re.I), 'unmanaged'),
    (re.compile(r'\b(mission|purpose|goal|what does .+ do)\b', re.I), 'mission'),
    (re.compile(r'\b(contact|reach|slack|email|how to contact)\b', re.I), 'contact'),
    (re.compile(r'\b(active teams?|how many teams?|list teams?)\b', re.I), 'list_teams'),
    (re.compile(r'\b(circular|cycle|loop)\b', re.I), 'circular'),
    (re.compile(r'\b(chain|path|how deep|longest)\b', re.I), 'chain'),
]


def _detect_intent(query: str) -> str:
    """Classify query into an intent key."""
    for pattern, intent in _INTENT_PATTERNS:
        if pattern.search(query):
            return intent
    return 'general'


def _extract_team_name(query: str) -> str | None:
    """Try to extract a team name from the query text."""
    from teams.models import Team
    q_lower = query.lower()
    best: tuple[int, str | None] = (0, None)
    for team in Team.objects.values('team_name'):
        name = team['team_name']
        # Score: number of name words found in query
        words = name.lower().split()
        score = sum(1 for w in words if w in q_lower)
        if score > best[0]:
            best = (score, name)
    return best[1] if best[0] > 0 else None


def ask_engie(query: str) -> dict[str, Any]:
    """
    Natural-language interface to the Engie knowledge base.

    Resolves queries like:
      "Who manages Platform Core?"
      "What breaks if Stream Ops fails?"
      "Which teams depend on Broadcast API?"
      "Show critical dependencies"
      "Teams without managers"

    Returns:
      {intent, answer, confidence, suggestion?}
    """
    from teams.models import Team
    from teams.queries import get_team_detail, search_teams, get_teams_without_managers

    query = (query or '').strip()
    if not query:
        return {'error': 'Empty query — please ask a question.'}

    intent = _detect_intent(query)
    team_name = _extract_team_name(query)
    answer: Any = {}

    logger.info('[AskEngie] query="%s" intent=%s team="%s"', query, intent, team_name)

    # ── OWNER ────────────────────────────────────────────────────
    if intent == 'owner':
        if team_name:
            teams = search_teams(query=team_name)
            if teams.exists():
                t = teams.first()
                answer = {
                    'team': t.team_name,
                    'manager': t.manager.full_name if t.manager else 'No manager assigned',
                    'department': t.department.department_name if t.department else 'Unknown',
                }
            else:
                answer = {'message': f'No team found matching "{team_name}".'}
        else:
            answer = {'message': 'Please mention a team name, e.g. "Who manages Platform Core?"'}

    # ── IMPACT ───────────────────────────────────────────────────
    elif intent == 'impact':
        if team_name:
            teams = search_teams(query=team_name)
            if teams.exists():
                t = teams.first()
                answer = predict_impact(t.pk)
            else:
                answer = {'message': f'No team found matching "{team_name}".'}
        else:
            answer = {'message': 'Mention a team name to predict impact, e.g. "What breaks if Platform Core fails?"'}

    # ── RISK ─────────────────────────────────────────────────────
    elif intent == 'risk':
        risks = detect_organisational_risks()
        critical = [r.to_dict() for r in risks if r.severity in ('critical', 'high')]
        answer = {
            'total_risks': len(risks),
            'critical_and_high': len(critical),
            'risks': critical[:5],
        }

    # ── UNMANAGED ────────────────────────────────────────────────
    elif intent == 'unmanaged':
        unmanaged = get_teams_without_managers()
        names = [t.team_name for t in unmanaged]
        answer = {
            'count': len(names),
            'teams': names,
            'message': f'{len(names)} team(s) have no manager assigned.' if names
                       else 'All active teams have managers assigned.',
        }

    # ── MISSION ──────────────────────────────────────────────────
    elif intent == 'mission':
        if team_name:
            teams = search_teams(query=team_name)
            if teams.exists():
                t = teams.first()
                answer = {
                    'team': t.team_name,
                    'mission': t.mission_purpose or 'No mission statement recorded.',
                    'description': t.description or '',
                }
            else:
                answer = {'message': f'No team found matching "{team_name}".'}
        else:
            answer = {'message': 'Mention a team name to query its mission.'}

    # ── CONTACT ──────────────────────────────────────────────────
    elif intent == 'contact':
        if team_name:
            teams = search_teams(query=team_name)
            if teams.exists():
                t = teams.first()
                answer = get_smart_contact(t.pk)
            else:
                answer = {'message': f'No team found matching "{team_name}".'}
        else:
            answer = {'message': 'Mention a team name for contact routing.'}

    # ── LIST_TEAMS ───────────────────────────────────────────────
    elif intent == 'list_teams':
        from teams.models import Team as T
        active = T.objects.filter(status='active').values_list('team_name', flat=True)
        answer = {
            'active_teams': list(active),
            'count': len(active),
        }

    # ── CIRCULAR ─────────────────────────────────────────────────
    elif intent == 'circular':
        cycles = detect_circular_dependencies()
        answer = {
            'cycles_found': len(cycles),
            'cycles': cycles[:5],
            'message': f'{len(cycles)} circular dependency cycle(s) detected.' if cycles
                       else 'No circular dependencies detected.',
        }

    # ── CHAIN ────────────────────────────────────────────────────
    elif intent == 'chain':
        if team_name:
            teams = search_teams(query=team_name)
            if teams.exists():
                t = teams.first()
                answer = get_dependency_chain(t.pk, direction='downstream')
            else:
                answer = {'message': f'No team found matching "{team_name}".'}
        else:
            answer = {'message': 'Mention a team name to trace its dependency chain.'}

    # ── GENERAL / FALLBACK ───────────────────────────────────────
    else:
        results = deep_search(query)
        if results['total']:
            top = results['results'][0]
            answer = {
                'top_result': top,
                'all_results': results['results'][:5],
                'message': f'Found {results["total"]} result(s) for "{query}".',
            }
        else:
            answer = {
                'message': f'No results found for "{query}". Try: "who manages X", "what breaks if Y fails", "show risks".',
            }
        intent = 'general'

    return {
        'query': query,
        'intent': intent,
        'answer': answer,
        'confidence': 'high' if team_name else 'medium',
    }


# ─────────────────────────────────────────────────────────────────
# 7. SMART CONTACT ROUTING
# ─────────────────────────────────────────────────────────────────

def get_smart_contact(team_id: int) -> dict[str, Any]:
    """
    "Who should I contact RIGHT NOW for this team?"

    Priority:
      1. Team manager (if active)
      2. Primary Slack contact
      3. Primary email contact
      4. Most recent active team member

    Returns structured routing answer.
    """
    from teams.models import Team, Contact, UserPosition

    try:
        team = Team.objects.select_related('manager').get(pk=team_id)
    except Team.DoesNotExist:
        return {'error': f'Team {team_id} not found.'}

    routing: list[dict] = []

    # 1 — Manager
    if team.manager:
        routing.append({
            'priority': 1,
            'role': 'Manager',
            'name': team.manager.full_name,
            'username': team.manager.username,
            'email': team.manager.email,
            'reason': 'Direct team manager — first point of contact.',
        })

    # 2 — Slack / Email contacts
    for contact in Contact.objects.filter(team=team, is_primary=True):
        routing.append({
            'priority': 2,
            'role': f'{contact.contact_type.capitalize()} channel',
            'name': contact.contact_value,
            'contact_type': contact.contact_type,
            'reason': f'Primary {contact.contact_type} channel for this team.',
        })

    # 3 — Fallback: active member
    if not team.manager:
        member = UserPosition.objects.filter(
            team=team, end_date__isnull=True
        ).select_related('user').first()
        if member:
            routing.append({
                'priority': 3,
                'role': member.job_title,
                'name': member.user.full_name,
                'email': member.user.email,
                'reason': 'Senior active team member — manager unassigned.',
            })

    return {
        'team_id': team_id,
        'team_name': team.team_name,
        'recommended': routing[0] if routing else None,
        'all_contacts': routing,
        'manager_assigned': team.manager is not None,
    }


# ─────────────────────────────────────────────────────────────────
# 8. ORGANISATION TIMELINE
# ─────────────────────────────────────────────────────────────────

def get_organisation_timeline(limit: int = 50) -> list[dict]:
    """
    Build a chronological history of the organisation from:
      - AuditLog (admin create/update/delete events)
      - TeamActivity (team-level events)

    Returns list of timeline entries sorted newest first.
    """
    from notifications.models import AuditLog
    from teams.models import TeamActivity

    entries: list[dict] = []

    # AuditLog entries
    for log in AuditLog.objects.select_related('actor').order_by('-timestamp')[:limit]:
        entries.append({
            'source': 'audit',
            'timestamp': log.timestamp.isoformat(),
            'actor': log.actor.full_name,
            'action': log.action,
            'entity_type': log.entity_type,
            'entity_id': log.entity_id,
            'entity_display': log.entity_display,
            'summary': f'{log.actor.full_name} {log.action}d {log.entity_type} "{log.entity_display}"',
            'old_values': log.old_values,
            'new_values': log.new_values,
        })

    # TeamActivity entries
    for act in TeamActivity.objects.select_related('team', 'user').order_by('-created_at')[:limit]:
        entries.append({
            'source': 'team_activity',
            'timestamp': act.created_at.isoformat(),
            'actor': act.user.full_name if act.user else 'System',
            'action': act.action_type,
            'entity_type': 'team',
            'entity_id': str(act.team.pk),
            'entity_display': act.team.team_name,
            'summary': act.description,
            'old_values': None,
            'new_values': None,
        })

    entries.sort(key=lambda e: e['timestamp'], reverse=True)
    return entries[:limit]
