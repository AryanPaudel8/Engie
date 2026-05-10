"""Team Dependency model for Engie."""
import logging
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

logger = logging.getLogger('engie')


class TeamDependency(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'
        RESOLVED = 'resolved', 'Resolved'

    class Criticality(models.TextChoices):
        LOW = 'low', 'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH = 'high', 'High'
        CRITICAL = 'critical', 'Critical'

    upstream_team = models.ForeignKey(
        'teams.Team', on_delete=models.CASCADE, related_name='upstream_dependencies',
        help_text='The team being depended ON (provides the service)',
    )
    downstream_team = models.ForeignKey(
        'teams.Team', on_delete=models.CASCADE, related_name='downstream_dependencies',
        help_text='The team that depends on upstream (consumes the service)',
    )
    dependency_type = models.CharField(max_length=50, blank=True, default='')
    description = models.TextField(blank=True, default='')
    criticality = models.CharField(max_length=20, choices=Criticality.choices, default=Criticality.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(default=timezone.now)
    last_verified = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Team Dependency'
        verbose_name_plural = 'Team Dependencies'
        ordering = ['-criticality']
        unique_together = [('upstream_team', 'downstream_team')]

    def __str__(self):
        return f'{self.downstream_team} depends on {self.upstream_team} [{self.criticality}]'

    def clean(self):
        if self.upstream_team_id == self.downstream_team_id:
            raise ValidationError('A team cannot depend on itself.')
