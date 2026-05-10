"""
User Authentication Services — Day 8

Handles all auth flows:
  - Register, Login, Logout
  - Password reset (token-based)
  - Profile updates (with audit trail)

All mutations write AuditLog entries.
"""
import secrets
import logging
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from users.models import UserAccount, PasswordResetToken
from notifications.models import AuditLog

logger = logging.getLogger('engie')


@transaction.atomic
def register_user(username, email, password, full_name, ip_address=None):
    """
    Register a new user account.
    Validates uniqueness of email and username.
    Returns the created UserAccount.
    """
    if not username or not username.strip():
        raise ValidationError({'username': 'Username is required.'})
    if not email or not email.strip():
        raise ValidationError({'email': 'Email is required.'})
    if not password or len(password) < 8:
        raise ValidationError({'password': 'Password must be at least 8 characters.'})
    if not full_name or not full_name.strip():
        raise ValidationError({'full_name': 'Full name is required.'})

    if UserAccount.objects.filter(email__iexact=email).exists():
        raise ValidationError({'email': 'An account with this email already exists.'})
    if UserAccount.objects.filter(username__iexact=username).exists():
        raise ValidationError({'username': 'This username is already taken.'})

    user = UserAccount.objects.create_user(
        email=email.lower().strip(),
        username=username.strip(),
        password=password,
        full_name=full_name.strip(),
    )

    AuditLog.objects.create(
        actor=user,
        action=AuditLog.Action.CREATE,
        entity_type='UserAccount',
        entity_id=str(user.pk),
        entity_display=str(user),
        new_values={'username': user.username, 'email': user.email},
        ip_address=ip_address,
    )

    logger.info(f'New user registered: {user.username} from {ip_address}')
    return user


def login_user(request, email, password, ip_address=None):
    """
    Authenticate and log in a user.
    Updates last_login and increments login_streak.
    Returns authenticated user or raises ValidationError.
    """
    user = authenticate(request, username=email, password=password)
    if not user:
        logger.warning(f'Failed login attempt for email={email} from {ip_address}')
        raise ValidationError('Invalid email or password.')

    if not user.is_active:
        raise ValidationError('This account has been deactivated.')

    login(request, user)

    # Update login timestamp and streak
    user.last_login = timezone.now()
    user.login_streak = (user.login_streak or 0) + 1
    user.save(update_fields=['last_login', 'login_streak'])

    AuditLog.objects.create(
        actor=user,
        action=AuditLog.Action.LOGIN,
        entity_type='UserAccount',
        entity_id=str(user.pk),
        entity_display=str(user),
        ip_address=ip_address,
    )

    logger.info(f'User logged in: {user.username} from {ip_address}')
    return user


def logout_user(request, ip_address=None):
    """Log out the current user and record the event."""
    user = request.user
    if user.is_authenticated:
        AuditLog.objects.create(
            actor=user,
            action=AuditLog.Action.LOGOUT,
            entity_type='UserAccount',
            entity_id=str(user.pk),
            entity_display=str(user),
            ip_address=ip_address,
        )
    logout(request)
    logger.info(f'User logged out: {getattr(user, "username", "anonymous")}')


@transaction.atomic
def generate_password_reset_token(email):
    """
    Generate a one-time password reset token for the given email.
    Returns the token string (caller is responsible for sending the email).
    If email is not found, returns None silently (security: don't reveal existence).
    """
    try:
        user = UserAccount.objects.get(email__iexact=email, is_active=True)
    except UserAccount.DoesNotExist:
        logger.info(f'Password reset requested for unknown email: {email}')
        return None  # Silent — don't reveal whether email exists

    # Invalidate old tokens
    PasswordResetToken.objects.filter(user=user, is_used=False).update(is_used=True)

    token_value = secrets.token_urlsafe(48)
    PasswordResetToken.objects.create(user=user, token=token_value)

    logger.info(f'Password reset token generated for: {user.username}')
    return token_value


@transaction.atomic
def reset_password_with_token(token_value, new_password, ip_address=None):
    """
    Validate a password reset token and update the user's password.
    Invalidates the token after use.
    Returns True on success, raises ValidationError on failure.
    """
    if not new_password or len(new_password) < 8:
        raise ValidationError({'password': 'Password must be at least 8 characters.'})

    try:
        token = PasswordResetToken.objects.select_related('user').get(token=token_value)
    except PasswordResetToken.DoesNotExist:
        raise ValidationError('Invalid or expired reset link.')

    if not token.is_valid():
        raise ValidationError('This reset link has expired. Please request a new one.')

    user = token.user
    user.set_password(new_password)
    user.save(update_fields=['password'])

    token.is_used = True
    token.save(update_fields=['is_used'])

    AuditLog.objects.create(
        actor=user,
        action=AuditLog.Action.PASSWORD_CHANGE,
        entity_type='UserAccount',
        entity_id=str(user.pk),
        entity_display=str(user),
        ip_address=ip_address,
    )

    logger.info(f'Password reset successful for: {user.username}')
    return True


@transaction.atomic
def update_profile(actor, user_id, ip_address=None, **fields):
    """
    Update a user's profile fields with audit trail.
    Users can only update their own profile (or admin updates any).
    """
    try:
        user = UserAccount.objects.get(pk=user_id)
    except UserAccount.DoesNotExist:
        raise ValidationError('User not found.')

    if actor.pk != user.pk and not actor.is_admin:
        raise ValidationError('You can only update your own profile.')

    allowed = {'full_name', 'phone_number', 'avatar_initials'}
    old_values = {f: getattr(user, f) for f in allowed}

    changed = {}
    for field, value in fields.items():
        if field in allowed and getattr(user, field) != value:
            setattr(user, field, value)
            changed[field] = value

    if not changed:
        return user

    user.full_clean()
    user.save()

    AuditLog.objects.create(
        actor=actor,
        action=AuditLog.Action.UPDATE,
        entity_type='UserAccount',
        entity_id=str(user.pk),
        entity_display=str(user),
        old_values=old_values,
        new_values={f: getattr(user, f) for f in allowed},
        ip_address=ip_address,
    )

    return user
