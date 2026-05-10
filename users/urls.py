from django.urls import path
from users import views

urlpatterns = [
    path('auth/register/', views.register_view, name='auth-register'),
    path('auth/login/', views.login_view, name='auth-login'),
    path('auth/logout/', views.logout_view, name='auth-logout'),
    path('auth/profile/', views.profile_view, name='auth-profile'),
    path('auth/forgot-password/', views.forgot_password_view, name='auth-forgot-password'),
    path('auth/reset-password/', views.reset_password_view, name='auth-reset-password'),
]
