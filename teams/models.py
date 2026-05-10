"""
Day 3 & 4 — Core Models: Team, Department, UserPosition, Repository

All models follow the ERD from the coursework CWK1 document.
Constraints (min 5 engineers, min 3 teams per dept) are enforced at the
model level via clean() and at the service level via the constraint engine.
"""

import logging
from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger('engie')


class Department(models.Model):
    """
    Represents an engineering department (e.g. Broadcast Engineering, Platform).

    Each department must have at least MIN_TEAMS_PER_DEPARTMENT teams
    (enforced by the constraint engine in services.py, not hard-blocked here
    to allow initial creation).

    Relationships:
        head_user  → UserAccount (the department head)
        teams      → reverse FK from Team
    """

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'
        ARCHIVED = 'archived', 'Archived'
        RESTRUCTURING = 'restructuring', 'Restructuring'
        DISBANDED = 'disbanded', 'Disbanded'

    head_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        related_name='headed_department',
        null=True,
        blank=True,
        help_text='The department head. Deletion blocked while they hold this role.',
    )
    department_name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True, default='')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    email_distribution = models.EmailField(max_length=100, blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = 'Department'
        verbose_name_plural = 'Departments'
        ordering = ['department_name']

    def __str__(self):
        return self.department_name

    @property
    def team_count(self):
        """Number of teams in this department."""
        return self.teams.filter(status=Team.Status.ACTIVE).count()

    @property
    def engineer_count(self):
        """Total engineers across all active teams."""
        return UserPosition.objects.filter(
            team__department=self,
            team__status=Team.Status.ACTIVE,
            end_date__isnull=True,
        ).count()


class Team(models.Model):
    """
    Core entity: an engineering team within a department.

    Business rules enforced:
        - Must have a manager (UserAccount)
        - Must belong to a department
        - Minimum 5 active engineers (enforced in constraint engine)
        - Cannot be deleted while it has active upstream dependencies

    Relationships:
        department        → Department
        manager           → UserAccount
        members           → UserPosition (reverse)
        upstream_deps     → TeamDependency (teams that depend ON this team)
        downstream_deps   → TeamDependency (teams this team depends on)
        repositories      → Repository (reverse)
        contacts          → Contact (reverse)
    """

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'
        ARCHIVED = 'archived', 'Archived'
        RESTRUCTURING = 'restructuring', 'Restructuring'
        DISBANDED = 'disbanded', 'Disbanded'

    department = models.ForeignKey(
        Department,
        on_delete=models.RESTRICT,
        related_name='teams',
        help_text='Department this team belongs to.',
    )
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        related_name='managed_teams',
        null=True,
        blank=True,
        help_text='Team manager. Null means team is unmanaged (flagged in reports).',
    )
    team_name = models.CharField(max_length=100, db_index=True)
    description = models.TextField(blank=True, default='')
    mission_purpose = models.TextField(blank=True, default='')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = 'Team'
        verbose_name_plural = 'Teams'
        ordering = ['team_name']
        unique_together = [('department', 'team_name')]

    def __str__(self):
        return f'{self.team_name} ({self.department})'

    def clean(self):
        """Validate team-level business rules."""
        if self.manager and not self.manager.is_active:
            raise ValidationError({'manager': 'Team manager must be an active user.'})

    @property
    def member_count(self):
        """Count of active members in this team."""
        return self.members.filter(end_date__isnull=True).count()

    @property
    def is_understaffed(self):
        """True if team has fewer than the minimum required engineers."""
        min_required = getattr(settings, 'ENGIE_MIN_ENGINEERS_PER_TEAM', 5)
        return self.member_count < min_required

    @property
    def is_unmanaged(self):
        """True if team has no assigned manager."""
        return self.manager is None

    @property
    def slack_channel(self):
        """Return the primary Slack contact for this team, if configured."""
        contact = self.contacts.filter(contact_type='slack', is_primary=True).first()
        return contact.contact_value if contact else None


class UserPosition(models.Model):
    """
    Junction model: a user's position/role within a team.

    A user can be a member of multiple teams (e.g. contractor embedded
    in two teams). The is_primary flag marks their main team.
    reporting_to tracks the user's direct manager within this team context.

    This model represents the 'engineers per team' count for constraint checks.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='positions',
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='members',
    )
    reporting_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='direct_reports',
    )
    job_title = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True, help_text='Null = currently active')
    is_primary = models.BooleanField(
        default=True,
        help_text='Is this the user\'s primary team?',
    )

    class Meta:
        verbose_name = 'User Position'
        verbose_name_plural = 'User Positions'
        ordering = ['-start_date']
        # Prevent duplicate active positions in the same team
        unique_together = [('user', 'team', 'start_date')]

    def __str__(self):
        status = 'active' if not self.end_date else 'former'
        return f'{self.user} → {self.team} [{self.job_title}] ({status})'

    def clean(self):
        """Ensure end_date is after start_date if provided."""
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({'end_date': 'End date cannot be before start date.'})

    @property
    def is_active(self):
        """True if the user is currently in this role."""
        return self.end_date is None


class Repository(models.Model):
    """
    A code repository linked to a team.
    One repository per team can be marked as the main repo (is_main=True).
    """

    class RepoType(models.TextChoices):
        GIT = 'git', 'Git'
        SVN = 'svn', 'SVN'
        OTHER = 'other', 'Other'

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='repositories')
    repo_name = models.CharField(max_length=100)
    repo_type = models.CharField(max_length=20, choices=RepoType.choices, default=RepoType.GIT)
    url = models.URLField(max_length=255, unique=True)
    is_main = models.BooleanField(default=False)
    description = models.TextField(blank=True, default='')
    last_commit_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = 'Repository'
        verbose_name_plural = 'Repositories'
        ordering = ['-is_main', 'repo_name']

    def __str__(self):
        return f'{self.repo_name} ({self.team})'

    def clean(self):
        """Enforce only one main repo per team."""
        if self.is_main:
            existing = Repository.objects.filter(
                team=self.team, is_main=True
            ).exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError({'is_main': 'A team can only have one main repository.'})


class Contact(models.Model):
    """
    A contact method for a team (email, phone, Slack, Jira board link, etc.)
    Only one primary contact per contact_type per team is allowed.
    """

    class ContactType(models.TextChoices):
        EMAIL = 'email', 'Email'
        PHONE = 'phone', 'Phone'
        SLACK = 'slack', 'Slack'
        JIRA = 'jira', 'Jira'

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='contacts')
    contact_type = models.CharField(max_length=20, choices=ContactType.choices)
    contact_value = models.CharField(max_length=100)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = 'Contact'
        verbose_name_plural = 'Contacts'
        ordering = ['-is_primary', 'contact_type']

    def __str__(self):
        return f'{self.team} — {self.contact_type}: {self.contact_value}'

    def clean(self):
        """Enforce only one primary per type per team."""
        if self.is_primary:
            existing = Contact.objects.filter(
                team=self.team,
                contact_type=self.contact_type,
                is_primary=True,
            ).exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError(
                    {'is_primary': f'Team already has a primary {self.contact_type} contact.'}
                )


class TeamActivity(models.Model):
    """
    Activity log specific to a team.
    Powers the 'Activity Feed' on the dashboard.
    Different from AuditLog — this is user-facing timeline, not security audit.
    """

    class ActionType(models.TextChoices):
        TEAM_CREATED = 'team_created', 'Team Created'
        TEAM_UPDATED = 'team_updated', 'Team Updated'
        MEMBER_JOINED = 'member_joined', 'Member Joined'
        MEMBER_LEFT = 'member_left', 'Member Left'
        DEP_ADDED = 'dep_added', 'Dependency Added'
        DEP_REMOVED = 'dep_removed', 'Dependency Removed'
        REPO_ADDED = 'repo_added', 'Repository Added'
        STATUS_CHANGED = 'status_changed', 'Status Changed'
        MANAGER_ASSIGNED = 'manager_assigned', 'Manager Assigned'

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='activities')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='team_activities',
    )
    action_type = models.CharField(max_length=30, choices=ActionType.choices, db_index=True)
    description = models.TextField()
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = 'Team Activity'
        verbose_name_plural = 'Team Activities'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['-created_at'])]

    def __str__(self):
        return f'[{self.team}] {self.action_type} by {self.user}'
