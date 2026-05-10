from django.urls import path
from scheduling import views

urlpatterns = [
    path('events/', views.events_view, name='events-list'),
    path('events/<int:event_id>/respond/', views.respond_to_invite_view, name='event-respond'),
]
