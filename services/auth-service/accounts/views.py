from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


from accounts.serializers import (
    LoginInputSerializer,
    LogoutInputSerializer,
    RegisterInputSerializer,
    UserOutputSerializer,
)

from accounts.services import AuthService




class RegisterAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = RegisterInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = AuthService.register_user(**serializer.validated_data)

        return Response(
            {
                'user': UserOutputSerializer(result['user']).data,
                'tokens': result['tokens'],
            },
            status=status.HTTP_201_CREATED,
        )




class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = LoginInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = AuthService.login_user(**serializer.validated_data)

        return Response(
            {
                'user': UserOutputSerializer(result['user']).data,
                'tokens': result['tokens'],
            },
            status=status.HTTP_200_OK,

        )




class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = LogoutInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        AuthService.logout_user(refresh_token=serializer.validated_data['refresh'])

        return Response(
            {'detail': 'Successfully logged out.'},
            status=status.HTTP_200_OK,
        )




class CurrentUserAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(
            UserOutputSerializer(request.user).data,
            status=status.HTTP_200_OK,
        )
