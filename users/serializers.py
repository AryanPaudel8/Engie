"""User Serializers"""
from rest_framework import serializers
from users.models import UserAccount


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAccount
        fields = ['id', 'username', 'email', 'full_name', 'phone_number',
                  'avatar_initials', 'role', 'is_active', 'created_at', 'last_login', 'login_streak']
        read_only_fields = ['id', 'created_at', 'last_login', 'login_streak']


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=50)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)
    full_name = serializers.CharField(max_length=100)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
