"""intelligence/urls.py — Intelligence Engine API routes"""
from django.urls import path
from intelligence import views

urlpatterns = [
    path('intelligence/risk/',              views.risk_view,                  name='intelligence-risk'),
    path('intelligence/impact/<int:team_id>/', views.impact_view,             name='intelligence-impact'),
    path('intelligence/circular/',          views.circular_view,              name='intelligence-circular'),
    path('intelligence/chain/<int:team_id>/', views.chain_view,               name='intelligence-chain'),
    path('intelligence/search/',            views.search_view,                name='intelligence-search'),
    path('intelligence/ask/',               views.ask_view,                   name='intelligence-ask'),
    path('intelligence/contact/<int:team_id>/', views.contact_view,           name='intelligence-contact'),
    path('intelligence/timeline/',          views.timeline_view,              name='intelligence-timeline'),
    path('intelligence/constraints/',       views.constraints_view,           name='intelligence-constraints'),
    path('intelligence/incident/<int:team_id>/', views.incident_view,         name='intelligence-incident'),
    path('intelligence/dashboard/',         views.intelligence_dashboard_view, name='intelligence-dashboard'),
]
