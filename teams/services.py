"""
Day 6 — Constraint Engine + Team Business Logic (Services Layer)

ALL business logic for teams lives here. Views call services.
Services call queries. Never the other way around.

Key features:
  - Constraint Engine: validates min engineers, min teams per dept
  - Audit trail integration: every mutation logs to AuditLog
  - Activity feed: key actions recorded as TeamActivity
  - Team CRUD with full validation
"""

import logging
from django.db import transaction
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone

from teams.models import Team, Department, UserPosition, Repository, Contact, TeamActivity
from teams import queries as team_queries
from notifications.models import AuditLog

logger = logging.getLogger('engie')

MIN_ENGINEERS = getattr(settings, 'ENGIE_MIN_ENGINEERS_PER_TEAM', 5)
MIN_TEAMS = getattr(settings, 'ENGIE_MIN_TEAMS_PER_DEPARTMENT', 3)


# ──────────────────────────────────────────────
# CONSTRAINT ENGINE
# ──────────────────────────────────────────────

class ConstraintViolation:
    """Represents a single constraint violation with severity."""
    def __init__(self, constraint_id, entity, message, severity='warning'):
        self.constraint_id = constraint_id
        self.entity = entity
        self.message = message
        self.severity = severity  # 'warning' | 'error'

    def to_dict(self):
        return {
            'constraint_id': self.constraint_id,
            'entity': self.entity,
            'message': self.message,
            'severity': self.severity,
        }


def validate_team_structure(team_id=None):
    """
    Check all active teams (or a specific team) against:
      - Minimum 5 engineers per team
      - Manager must be assigned

    Returns a list of ConstraintViolation objects.
    Called by the dashboard and constraint engine endpoint.
    """
    violations = []

    teams_qs = team_queries.get_teams_with_member_counts()
    if team_id:
        teams_qs = teams_qs.filter(pk=team_id)

    for team in teams_qs.filter(status=Team.Status.ACTIVE):
        # Check minimum engineers
        if team.active_member_count < MIN_ENGINEERS:
            violations.append(ConstraintViolation(
                constraint_id='MIN_ENGINEERS',
                entity=f'Team: {team.team_name}',
                message=(
                    f'Team "{team.team_name}" has {team.active_member_count} engineer(s). '
                    f'Minimum required: {MIN_ENGINEERS}.'
                ),
                severity='warning' if team.active_member_count >= 3 else 'error',
            ))

        # Check manager assigned
        if team.manager is None:
            violations.append(ConstraintViolation(
                constraint_id='NO_MANAGER',
                entity=f'Team: {team.team_name}',
                message=f'Team "{team.team_name}" has no assigned manager.',
                severity='warning',
            ))

    return violations


def validate_department_strength(department_id=None):
    """
    Check all departments (or a specific one) against:
      - Minimum 3 active teams per department

    Returns a list of ConstraintViolation objects.
    """
    violations = []

    dept_qs = team_queries.get_department_stats()
    if department_id:
        dept_qs = dept_qs.filter(pk=department_id)

    for dept in dept_qs:
        if dept.active_teams_count < MIN_TEAMS:
            violations.append(ConstraintViolation(
                constraint_id='MIN_TEAMS_PER_DEPT',
                entity=f'Department: {dept.department_name}',
                message=(
                    f'Department "{dept.department_name}" has {dept.active_teams_count} active team(s). '
                    f'Minimum required: {MIN_TEAMS}.'
                ),
                severity='warning' if dept.team_count >= 1 else 'error',
            ))

    return violations


def run_full_constraint_check():
    """
    Run all constraint checks across the entire system.
    Returns a combined list of all violations, sorted by severity.

    Called by: /api/intelligence/constraints/ endpoint.
    """
    violations = validate_team_structure() + validate_department_strength()
    # Sort: errors first, then warnings
    violations.sort(key=lambda v: (0 if v.severity == 'error' else 1, v.entity))
    logger.info(f'Constraint check complete. {len(violations)} violation(s) found.')
    return violations


# ──────────────────────────────────────────────
# AUDIT HELPER
# ──────────────────────────────────────────────

def _write_audit_log(actor, action, entity_type, entity_id, entity_display='',
                     old_values=None, new_values=None, ip_address=None):
    """
    Internal helper: write a single AuditLog entry.
    Always called within a transaction to ensure atomicity.
    """
    try:
        AuditLog.objects.create(
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            entity_display=entity_display,
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address,
        )
    except Exception as e:
        logger.error(f'Failed to write audit log: {e}')


def _record_team_activity(team, user, action_type, description):
    """Record a team activity feed entry."""
    try:
        TeamActivity.objects.create(
            team=team,
            user=user,
            action_type=action_type,
            description=description,
        )
    except Exception as e:
        logger.error(f'Failed to record team activity: {e}')


# ──────────────────────────────────────────────
# TEAM CRUD SERVICES
# ──────────────────────────────────────────────

@transaction.atomic
def create_team(actor, department_id, manager_id=None, team_name=None,
                description='', mission_purpose='', ip_address=None):
    """
    Create a new team with full validation.

    Validates:
      - department exists
      - manager (if provided) is an active user
      - team_name is not blank

    Writes:
      - AuditLog entry (create)
      - TeamActivity entry

    Returns:
      team instance on success
      raises ValidationError on failure
    """
    if not team_name or not team_name.strip():
        raise ValidationError({'team_name': 'Team name is required.'})

    try:
        department = Department.objects.get(pk=department_id)
    except Department.DoesNotExist:
        raise ValidationError({'department': f'Department {department_id} does not exist.'})

    manager = None
    if manager_id:
        from users.models import UserAccount
        try:
            manager = UserAccount.objects.get(pk=manager_id, is_active=True)
        except UserAccount.DoesNotExist:
            raise ValidationError({'manager': 'Manager not found or inactive.'})

    team = Team(
        department=department,
        manager=manager,
        team_name=team_name.strip(),
        description=description,
        mission_purpose=mission_purpose,
    )
    team.full_clean()
    team.save()

    _write_audit_log(
        actor=actor,
        action=AuditLog.Action.CREATE,
        entity_type='Team',
        entity_id=team.pk,
        entity_display=str(team),
        new_values={'team_name': team.team_name, 'department': department.department_name},
        ip_address=ip_address,
    )

    _record_team_activity(
        team=team,
        user=actor,
        action_type=TeamActivity.ActionType.TEAM_CREATED,
        description=f'Team "{team.team_name}" created in {department.department_name}.',
    )

    logger.info(f'Team created: {team} by {actor}')
    return team


@transaction.atomic
def update_team(actor, team_id, ip_address=None, **update_fields):
    """
    Update a team's fields with audit logging.
    Only updates fields that are explicitly passed.

    Captures old/new values for the audit trail (Organisational Timeline).
    Returns updated team or raises ValidationError.
    """
    team = team_queries.get_team_detail(team_id)
    if not team:
        raise ValidationError({'team': f'Team {team_id} not found.'})

    # Capture old state for audit
    old_values = {
        'team_name': team.team_name,
        'description': team.description,
        'mission_purpose': team.mission_purpose,
        'status': team.status,
        'manager_id': team.manager_id,
    }

    allowed_fields = {'team_name', 'description', 'mission_purpose', 'status', 'manager_id'}
    changed = {}

    for field, value in update_fields.items():
        if field not in allowed_fields:
            continue
        if field == 'manager_id' and value is not None:
            from users.models import UserAccount
            try:
                manager = UserAccount.objects.get(pk=value, is_active=True)
                old_manager_id = team.manager_id
                team.manager = manager
                if old_manager_id != value:
                    changed['manager_id'] = value
                    _record_team_activity(
                        team=team,
                        user=actor,
                        action_type=TeamActivity.ActionType.MANAGER_ASSIGNED,
                        description=f'Manager changed to {manager.full_name}.',
                    )
            except UserAccount.DoesNotExist:
                raise ValidationError({'manager': 'Manager not found or inactive.'})
        elif field == 'status':
            old_status = team.status
            setattr(team, field, value)
            if old_status != value:
                changed[field] = value
                _record_team_activity(
                    team=team,
                    user=actor,
                    action_type=TeamActivity.ActionType.STATUS_CHANGED,
                    description=f'Status changed from {old_status} to {value}.',
                )
        else:
            old_val = getattr(team, field, None)
            setattr(team, field, value)
            if old_val != value:
                changed[field] = value

    if not changed:
        return team  # Nothing to update

    team.full_clean()
    team.save()

    new_values = {k: getattr(team, k) for k in old_values}

    _write_audit_log(
        actor=actor,
        action=AuditLog.Action.UPDATE,
        entity_type='Team',
        entity_id=team.pk,
        entity_display=str(team),
        old_values=old_values,
        new_values=new_values,
        ip_address=ip_address,
    )

    logger.info(f'Team updated: {team} by {actor}. Changed: {changed}')
    return team


@transaction.atomic
def delete_team(actor, team_id, ip_address=None):
    """
    Soft-delete a team by setting status to DISBANDED.
    Hard deletion is blocked if the team has active upstream dependencies.

    Returns True on success, raises ValidationError if blocked.
    """
    team = team_queries.get_team_detail(team_id)
    if not team:
        raise ValidationError({'team': f'Team {team_id} not found.'})

    # Block deletion if other teams depend on this team
    from dependencies.models import TeamDependency
    blocking_deps = TeamDependency.objects.filter(
        upstream_team=team,
        status=TeamDependency.Status.ACTIVE,
    )

    if blocking_deps.exists():
        dependents = list(blocking_deps.values_list('downstream_team__team_name', flat=True))
        raise ValidationError({
            'dependencies': (
                f'Cannot delete team "{team.team_name}". '
                f'The following teams depend on it: {", ".join(dependents)}. '
                'Remove or resolve those dependencies first.'
            )
        })

    old_status = team.status
    team.status = Team.Status.DISBANDED
    team.save(update_fields=['status'])

    _write_audit_log(
        actor=actor,
        action=AuditLog.Action.DELETE,
        entity_type='Team',
        entity_id=team.pk,
        entity_display=str(team),
        old_values={'status': old_status},
        new_values={'status': Team.Status.DISBANDED},
        ip_address=ip_address,
    )

    _record_team_activity(
        team=team,
        user=actor,
        action_type=TeamActivity.ActionType.STATUS_CHANGED,
        description=f'Team "{team.team_name}" was disbanded.',
    )

    logger.warning(f'Team disbanded: {team} by {actor}')
    return True


@transaction.atomic
def add_member_to_team(actor, team_id, user_id, job_title, start_date,
                       is_primary=True, reporting_to_id=None, ip_address=None):
    """
    Add a user to a team as a UserPosition.
    Logs the action and records team activity.
    Does NOT enforce the minimum 5 members — that's the constraint engine's job
    (it warns, not blocks).
    """
    from users.models import UserAccount

    team = team_queries.get_team_detail(team_id)
    if not team:
        raise ValidationError({'team': f'Team {team_id} not found.'})

    try:
        user = UserAccount.objects.get(pk=user_id, is_active=True)
    except UserAccount.DoesNotExist:
        raise ValidationError({'user': 'User not found or inactive.'})

    # Check not already an active member
    existing = UserPosition.objects.filter(
        user=user, team=team, end_date__isnull=True
    ).exists()
    if existing:
        raise ValidationError({'user': f'{user.full_name} is already an active member of {team.team_name}.'})

    reporting_to = None
    if reporting_to_id:
        try:
            reporting_to = UserAccount.objects.get(pk=reporting_to_id, is_active=True)
        except UserAccount.DoesNotExist:
            raise ValidationError({'reporting_to': 'Reporting-to user not found.'})

    position = UserPosition(
        user=user,
        team=team,
        reporting_to=reporting_to,
        job_title=job_title,
        start_date=start_date,
        is_primary=is_primary,
    )
    position.full_clean()
    position.save()

    _record_team_activity(
        team=team,
        user=actor,
        action_type=TeamActivity.ActionType.MEMBER_JOINED,
        description=f'{user.full_name} joined as {job_title}.',
    )

    _write_audit_log(
        actor=actor,
        action=AuditLog.Action.CREATE,
        entity_type='UserPosition',
        entity_id=position.pk,
        entity_display=str(position),
        new_values={'user': user.username, 'team': team.team_name, 'job_title': job_title},
        ip_address=ip_address,
    )

    logger.info(f'Member added: {user} to {team} as {job_title} by {actor}')
    return position
