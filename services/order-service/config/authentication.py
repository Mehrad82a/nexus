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

