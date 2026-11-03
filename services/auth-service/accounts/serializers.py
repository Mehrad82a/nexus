from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from accounts.models import User



class UserOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'role',
            'is_verified',
            'created_at',
        ]
        read_only_fields = fields



class RegisterInputSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True, style={'input_type': 'password'})

    first_name = serializers.CharField(required=True, max_length=150)
    last_name = serializers.CharField(required=True, max_length=150)

    def validate_password(self, value) -> str:
        validate_password(value)
        return value



class LoginInputSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True, style={'input_type': 'password'})


class LogoutInputSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=True)

