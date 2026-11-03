import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from accounts.models import User



@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def user_payload() -> dict:
    return {
        'email': 'mohamad@nexus.io',
        'password': 'StrongPassword123!',
        'first_name': 'Mohamad',
        'last_name': 'Abbasi',
    }


@pytest.mark.django_db
class TestAuthServiceAPI:
    def test_register_user_success(self, api_client: APIClient, user_payload: dict):
        url = reverse('accounts:register')
        response = api_client.post(url, data=user_payload, format='json')


        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['user']['email'] == user_payload['email']
        assert response.data['user']['role'] == User.Role.CUSTOMER
        assert 'access' in response.data['tokens']
        assert 'refresh' in response.data['tokens']
        assert User.objects.filter(email=user_payload['email']).exists()



    def test_register_duplicate_email_fails(self, api_client: APIClient, user_payload: dict):
        url = reverse('accounts:register')
        api_client.post(url, data=user_payload, format='json')

        response = api_client.post(url, data=user_payload, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'email' in response.data



    def test_login_user_success(self, api_client: APIClient, user_payload: dict):
        User.objects.create_user(**user_payload)
        url = reverse('accounts:login')

        response = api_client.post(
            url,
            data={'email': user_payload['email'], 'password': user_payload['password']},
            format='json'
        )

        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data['tokens']
        assert 'refresh' in response.data['tokens']



    def test_current_user_me_endpoint_requires_jwt(self, api_client: APIClient, user_payload: dict):
        me_url = reverse('accounts:current_user')

        unauth_res = api_client.get(me_url)

        assert unauth_res.status_code == status.HTTP_401_UNAUTHORIZED

        register_res = api_client.post(reverse('accounts:register'), data=user_payload, format='json')
        assess_token = register_res.data['tokens']['access']

        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {assess_token}')
        auth_res = api_client.get(me_url)

        assert auth_res.status_code == status.HTTP_200_OK
        assert auth_res.data['email'] == user_payload['email']



    def test_logout_blacklists_refresh_token(self, api_client: APIClient, user_payload: dict):
        register_res = api_client.post(reverse('accounts:register'), data=user_payload, format='json')
        access_token = register_res.data['tokens']['access']
        refresh_token = register_res.data['tokens']['refresh']

        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        logout_res = api_client.post(
            reverse('accounts:logout'),
            data={'refresh': refresh_token},
            format='json',
        )

        assert logout_res.status_code == status.HTTP_200_OK

        refresh_res = api_client.post(
            reverse('accounts:token_refresh'),
            data={'refresh': refresh_token},
            format='json',
        )

        assert refresh_res.status_code == status.HTTP_401_UNAUTHORIZED



