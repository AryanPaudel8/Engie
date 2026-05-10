from django.urls import path
from teams import views

urlpatterns = [
    path('dashboard/', views.dashboard_stats_view, name='dashboard'),
    path('teams/', views.teams_list_view, name='teams-list'),
    path('teams/<int:team_id>/', views.team_detail_view, name='team-detail'),
    path('departments/', views.departments_list_view, name='departments-list'),
    path('departments/stats/', views.department_stats_view, name='department-stats'),
    path('departments/<int:dept_id>/', views.department_detail_view, name='department-detail'),
    path('reports/', views.reports_view, name='reports'),
    path('users/', views.users_list_view, name='users-list'),
]
