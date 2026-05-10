from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from users.models import UserAccount, PasswordResetToken


@admin.register(UserAccount)
class UserAccountAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'full_name', 'role', 'is_active', 'created_at', 'last_login']
    list_filter = ['role', 'is_active', 'is_staff']
    search_fields = ['username', 'email', 'full_name']
    ordering = ['full_name']
    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'phone_number', 'avatar_initials')}),
        ('Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Timestamps', {'fields': ('created_at', 'last_login', 'login_streak'), 'classes': ('collapse',)}),
    )
    add_fieldsets = (
        (None, {'classes': ('wide',), 'fields': ('email', 'username', 'full_name', 'password1', 'password2', 'role')}),
    )
    readonly_fields = ['created_at', 'last_login', 'login_streak']


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ['user', 'created_at', 'is_used']
    list_filter = ['is_used']
    readonly_fields = ['token', 'created_at']
