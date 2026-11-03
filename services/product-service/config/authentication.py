from rest_framework import permissions
from rest_framework_simplejwt.authentication import JWTStatelessUserAuthentication
from rest_framework_simplejwt.models import TokenUser


class StatelessUser(TokenUser):
    """
    Represents an authenticated user extracted purely from a verified JWT payload
    without querying a local User database table.
    """

    @property
    def role(self) -> str:
        return self.token.get('role', 'CUSTOMER')

    @property
    def email(self) -> str:
        return self.token.get('email', '')



class MicroserviceJWTAuthentication(JWTStatelessUserAuthentication):
    """
    Stateless JWT authentication across microservices using the shared JWT_SECRET_KEY.
    """

    def get_user(self, validated_token):
        return StatelessUser(validated_token)




class IsAdminRoleOrReadOnly(permissions.BasePermission):
    """
    Allows public read-only access (GET, HEAD, OPTIONS) to anyone,
    but restricts write operations (POST, PUT, PATCH, DELETE) strictly to ADMIN users.
    """

    def has_permission(self, request, view) -> bool:
        if request.method in permissions.SAFE_METHODS:
            return True

        return bool(
            request.user
            and request.user.is_authenticated()
            and getattr(request.user, 'role', None) == 'ADMIN'
        )


