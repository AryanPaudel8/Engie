"""
dependencies/services.py
=========================
Service layer for TeamDependency creation and management.

Handles:
  - Circular dependency prevention (calls intelligence.services.detect_circular_dependencies)
  - Audit logging on create/delete
  - Self-dependency rejection
"""
import logging
from django.core.exceptions import ValidationError
from django.utils import timezone

from dependencies.models import TeamDependency

logger = logging.getLogger('engie')


def create_dependency(
    actor,
    upstream_team_id: int,
    downstream_team_id: int,
    dependency_type: str = '',
    description: str = '',
    criticality: str = 'medium',
) -> TeamDependency:
    """
    Create a TeamDependency with full validation.

    Raises ValidationError if:
      - upstream == downstream (self-dependency)
      - duplicate dependency already exists
      - creating this dependency would form a circular chain
    """
    from teams.models import Team

    # ── Self-dependency check ────────────────────────────────────
    if upstream_team_id == downstream_team_id:
        raise ValidationError({'dependency': 'A team cannot depend on itself.'})

    # ── Duplicate check ─────────────────────────────────────────
    if TeamDependency.objects.filter(
        upstream_team_id=upstream_team_id,
        downstream_team_id=downstream_team_id,
    ).exists():
        raise ValidationError({'duplicate': 'This dependency relationship already exists.'})

    # ── Create the dependency ────────────────────────────────────
    try:
        upstream = Team.objects.get(pk=upstream_team_id)
        downstream = Team.objects.get(pk=downstream_team_id)
    except Team.DoesNotExist as exc:
        raise ValidationError({'team': f'Team not found: {exc}'})

    dep = TeamDependency.objects.create(
        upstream_team=upstream,
        downstream_team=downstream,
        dependency_type=dependency_type,
        description=description,
        criticality=criticality,
        status=TeamDependency.Status.ACTIVE,
    )

    # ── Circular check (post-create, then rollback if found) ─────
    from intelligence.services import detect_circular_dependencies
    cycles = detect_circular_dependencies()
    if cycles:
        dep.delete()
        raise ValidationError({
            'circular': f'Creating this dependency would form a circular chain: '
                        f'{" → ".join(cycles[0]["cycle"])}',
        })

    # ── Audit log ────────────────────────────────────────────────
    try:
        from notifications.models import AuditLog
        AuditLog.objects.create(
            actor=actor,
            action=AuditLog.Action.CREATE,
            entity_type='TeamDependency',
            entity_id=str(dep.pk),
            entity_display=f'{downstream.team_name} → {upstream.team_name}',
            new_values={
                'upstream': upstream.team_name,
                'downstream': downstream.team_name,
                'criticality': criticality,
            },
        )
    except Exception as exc:
        logger.warning('[DependencyService] Audit log failed: %s', exc)

    logger.info(
        '[DependencyService] Created dependency: %s → %s [%s] by %s',
        downstream.team_name, upstream.team_name, criticality, actor,
    )
    return dep


def delete_dependency(actor, dependency_id: int) -> None:
    """
    Delete a TeamDependency. Audit-logged.
    """
    try:
        dep = TeamDependency.objects.select_related(
            'upstream_team', 'downstream_team'
        ).get(pk=dependency_id)
    except TeamDependency.DoesNotExist:
        raise ValidationError({'dependency': 'Dependency not found.'})

    display = f'{dep.downstream_team.team_name} → {dep.upstream_team.team_name}'
    dep.delete()

    try:
        from notifications.models import AuditLog
        AuditLog.objects.create(
            actor=actor,
            action=AuditLog.Action.DELETE,
            entity_type='TeamDependency',
            entity_id=str(dependency_id),
            entity_display=display,
        )
    except Exception as exc:
        logger.warning('[DependencyService] Audit log failed: %s', exc)

    logger.info('[DependencyService] Deleted dependency %s by %s', dependency_id, actor)
