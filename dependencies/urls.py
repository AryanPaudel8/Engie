from django.urls import path
from dependencies import views

urlpatterns = [
    path('dependencies/', views.dependencies_view, name='dependencies'),
    path('dependencies/<int:dep_id>/', views.dependency_detail_view, name='dependency-detail'),
    path('teams/<int:team_id>/dependencies/', views.team_dependencies_view, name='team-dependencies'),
]
