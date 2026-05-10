"""
Auth API Views — Engie Engineering Registry
All views are thin wrappers around services. No business logic lives here.
"""
import logging
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth import update_session_auth_hash
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError

from users import services as user_services
from users.serializers import UserSerializer, RegisterSerializer, LoginSerializer

logger = logging.getLogger('engie')


def _get_ip(request):
    """Extract the client IP address from the request."""
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


@ensure_csrf_cookie
@api_view(['POST'])
@permission_classes([AllowAny])
def register_view(request):
    """POST /api/auth/register/ — Register a new user account."""
    serializer = RegisterSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = user_services.register_user(
            username=serializer.validated_data['username'],
            email=serializer.validated_data['email'],
            password=serializer.validated_data['password'],
            full_name=serializer.validated_data['full_name'],
            ip_address=_get_ip(request),
        )
        return Response(
            {'message': 'Account created successfully.', 'user': UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )
    except ValidationError as e:
        return Response({'errors': e.message_dict}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """POST /api/auth/login/ — Authenticate user and establish a session."""
    serializer = LoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = user_services.login_user(
            request=request,
            email=serializer.validated_data['email'],
            password=serializer.validated_data['password'],
            ip_address=_get_ip(request),
        )
        return Response({'message': 'Login successful.', 'user': UserSerializer(user).data})
    except ValidationError as e:
        return Response(
            {'errors': {'non_field_errors': [str(e.message)]}},
            status=status.HTTP_401_UNAUTHORIZED,
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """POST /api/auth/logout/"""
    user_services.logout_user(request, ip_address=_get_ip(request))
    return Response({'message': 'Logged out successfully.'})


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def profile_view(request):
    """
    GET  /api/auth/profile/  — return current user's profile
    PATCH /api/auth/profile/ — update profile fields OR change password
    """
    if request.method == 'GET':
        return Response(UserSerializer(request.user).data)

    # ── Password change branch ────────────────────────────────────────────
    if 'current_password' in request.data or 'new_password' in request.data:
        current_password = request.data.get('current_password', '')
        new_password = request.data.get('new_password', '')

        if not current_password or not new_password:
            return Response(
                {'errors': {'detail': 'Both current_password and new_password are required.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(new_password) < 8:
            return Response(
                {'errors': {'detail': 'Password must be at least 8 characters.'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = request.user
        if not user.check_password(current_password):
            return Response(
                {'errors': {'current_password': ['Current password is incorrect.']}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(new_password)
        user.save()
        # Keep the session alive after password change
        update_session_auth_hash(request, user)
        logger.info(f'Password changed for: {user.username}')
        return Response({'message': 'Password updated successfully.', 'user': UserSerializer(user).data})

    # ── Profile fields update branch ──────────────────────────────────────
    from users.models import UserAccount
    user = request.user
    errors = {}

    full_name = request.data.get('full_name', '').strip()
    username = request.data.get('username', '').strip()
    email = request.data.get('email', '').strip()

    if full_name:
        user.full_name = full_name

    if username and username != user.username:
        if UserAccount.objects.filter(username__iexact=username).exclude(pk=user.pk).exists():
            errors['username'] = ['This username is already taken.']
        else:
            user.username = username

    if email and email.lower() != user.email.lower():
        if UserAccount.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
            errors['email'] = ['An account with this email already exists.']
        else:
            user.email = email.lower()

    if errors:
        return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user.full_clean()
        user.save()
    except ValidationError as e:
        return Response({'errors': e.message_dict}, status=status.HTTP_400_BAD_REQUEST)

    logger.info(f'Profile updated for: {user.username}')
    return Response({'message': 'Profile updated.', 'user': UserSerializer(user).data})


@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password_view(request):
    """POST /api/auth/forgot-password/ — send reset token"""
    email = request.data.get('email', '').strip()
    if not email:
        return Response({'errors': {'email': ['Email is required.']}}, status=status.HTTP_400_BAD_REQUEST)
    user_services.generate_password_reset_token(email)
    return Response({'message': 'If an account exists, a reset link has been sent.'})


@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password_view(request):
    """POST /api/auth/reset-password/ — validate token and set new password"""
    token = request.data.get('token', '').strip()
    new_password = request.data.get('password', '')
    if not token or not new_password:
        return Response(
            {'errors': {'detail': 'Token and new password are required.'}},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        user_services.reset_password_with_token(
            token_value=token,
            new_password=new_password,
            ip_address=_get_ip(request),
        )
        return Response({'message': 'Password updated successfully. Please sign in.'})
    except ValidationError as e:
        return Response({'errors': {'detail': str(e.message)}}, status=status.HTTP_400_BAD_REQUEST)
