from django.urls import path
from messaging import views

urlpatterns = [
    path('messages/', views.messages_view, name='messages'),
    path('messages/unread-count/', views.unread_count_view, name='messages-unread'),
    path('messages/<int:msg_id>/', views.message_detail_view, name='message-detail'),
]
