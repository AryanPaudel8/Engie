from django.contrib import admin
from dependencies.models import TeamDependency

@admin.register(TeamDependency)
class TeamDependencyAdmin(admin.ModelAdmin):
    list_display = ['upstream_team', 'downstream_team', 'criticality', 'status', 'created_at']
    list_filter = ['criticality', 'status']
