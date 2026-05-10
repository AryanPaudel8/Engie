from django.urls import path
from notifications import views

urlpatterns = [
    path('notifications/', views.notifications_view, name='notifications'),
    path('notifications/<int:notif_id>/read/', views.mark_notification_read_view, name='notif-read'),
    path('notifications/read-all/', views.mark_all_read_view, name='notif-read-all'),
    path('audit/', views.audit_log_view, name='audit-log'),
]
