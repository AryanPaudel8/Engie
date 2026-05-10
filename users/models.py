"""
Day 2 — User Model + Auth Base

Custom UserAccount model extending AbstractBaseUser for full control over
authentication fields. Includes avatar initials, login streak tracking,
and role-based access (engineer / manager / admin).
"""

import logging
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone

logger = logging.getLogger('engie')


class UserAccountManager(BaseUserManager):
    """
    Custom manager for UserAccount.
    Overrides create_user and create_superuser to use email as the
    unique identifier instead of username.
    """

    def create_user(self, email, username, password=None, **extra_fields):
        """Create and return a regular user with email and password."""
        if not email:
            raise ValueError('Email address is required')
        if not username:
            raise ValueError('Username is required')

        email = self.normalize_email(email)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', UserAccount.Role.ENGINEER)

        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        logger.info(f'UserAccount created: {username} ({email})')
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        """Create and return a superuser with all permissions."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', UserAccount.Role.ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, username, password, **extra_fields)


class UserAccount(AbstractBaseUser, PermissionsMixin):
    """
    Central user model for Engie.

    Replaces Django's default User with email-based auth.
    Stores avatar initials, role, and login streak for dashboard stats.

    Roles:
        ENGINEER  — Standard authenticated user (read + message + schedule)
        MANAGER   — Can manage own team dependencies
        ADMIN     — Full platform access
    """

    class Role(models.TextChoices):
        ENGINEER = 'engineer', 'Engineer'
        MANAGER = 'manager', 'Manager'
        ADMIN = 'admin', 'Admin'

    # Core identity
    username = models.CharField(max_length=50, unique=True)
    email = models.EmailField(max_length=100, unique=True)
    full_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20, blank=True, default='')
    avatar_initials = models.CharField(max_length=5, blank=True, default='')

    # Role & status
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.ENGINEER,
        db_index=True,
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(null=True, blank=True)

    # Login streak — used on profile dashboard
    login_streak = models.PositiveIntegerField(default=0)

    objects = UserAccountManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'full_name']

    class Meta:
        verbose_name = 'User Account'
        verbose_name_plural = 'User Accounts'
        ordering = ['full_name']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['username']),
            models.Index(fields=['role']),
        ]

    def __str__(self):
        return f'{self.full_name} (@{self.username})'

    def save(self, *args, **kwargs):
        """Auto-generate avatar initials from full_name on save."""
        if self.full_name and not self.avatar_initials:
            parts = self.full_name.strip().split()
            self.avatar_initials = ''.join(p[0].upper() for p in parts[:2])
        super().save(*args, **kwargs)

    @property
    def is_admin(self):
        """Convenience check for admin role."""
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def is_manager(self):
        """Convenience check for manager or above."""
        return self.role in (self.Role.MANAGER, self.Role.ADMIN) or self.is_superuser

    def get_display_name(self):
        """Return full name or username as fallback."""
        return self.full_name or self.username


class PasswordResetToken(models.Model):
    """
    One-time token for password reset flow.
    Token is invalidated after use or after 24 hours.
    """

    user = models.ForeignKey(
        UserAccount,
        on_delete=models.CASCADE,
        related_name='password_reset_tokens',
    )
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    is_used = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Password Reset Token'
        ordering = ['-created_at']

    def __str__(self):
        return f'Reset token for {self.user.email}'

    def is_expired(self):
        """Token expires after 24 hours."""
        from datetime import timedelta
        return timezone.now() > self.created_at + timedelta(hours=24)

    def is_valid(self):
        """Token is valid if not used and not expired."""
        return not self.is_used and not self.is_expired()
