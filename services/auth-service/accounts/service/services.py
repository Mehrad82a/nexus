from typing import Dict, Any
from django.contrib.auth import authenticate
from django.db import transaction
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from accounts.models import User
from accounts.selectors import get_user_by_email


class AuthService:
    """
    Service layer encapsulating all authentication & identity business logic.
    """

    @staticmethod
    def _generate_tokens_for_user(user: User) -> Dict[str, str]:
        refresh = RefreshToken.for_user(user)

        refresh['email'] = user.email
        refresh['role'] = user.role

        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }



    @classmethod
    @transaction.atomic
    def register_user(
            cls,
            *,
            email: str,
            password: str,
            first_name: str = '',
            last_name: str = '',

    ) -> Dict[str, Any]:

        if get_user_by_email(email=email):
            raise ValidationError({'email': 'A user with this email already exists.'})

        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=User.Role.CUSTOMER,
        )

        tokens = cls._generate_tokens_for_user(user)

        return {
            'user': user,
            'tokens': tokens,
        }



    @classmethod
    def login_user(cls, *, email: str, password: str) -> Dict[str, Any]:
        user = authenticate(username=email, password=password)

        if not user:
            raise AuthenticationFailed('Invalid email or password.')

        if not user.is_active:
            raise AuthenticationFailed('User account is disabled.')

        tokens = cls._generate_tokens_for_user(user)

        return {
            'user': user,
            'tokens': tokens,
        }



    @staticmethod
    def logout_user(*, refresh_token: str) -> None:
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()

        except TokenError as exc:
            raise ValidationError({'refresh': 'Invalid or expired refresh token.'}) from exc



