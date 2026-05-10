"""Engie URL Configuration"""
from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from django.views.decorators.csrf import ensure_csrf_cookie
import os

@ensure_csrf_cookie
def index_view(request):
    """Serve the single-page frontend."""
    template_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 'templates', 'engie_complete.html'
    )
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return HttpResponse(content, content_type='text/html')

urlpatterns = [
    path('', index_view, name='index'),
    path('admin/', admin.site.urls),
    path('api/', include('users.urls')),
    path('api/', include('teams.urls')),
    path('api/', include('scheduling.urls')),
    path('api/', include('messaging.urls')),
    path('api/', include('notifications.urls')),
    path('api/', include('dependencies.urls')),
    path('api/', include('intelligence.urls')),
]
