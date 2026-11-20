import hashlib
import hmac
from dataclasses import dataclass
from uuid import UUID
import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings


bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: UUID
    email: str
    role: str



def get_current_user(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)
) -> AuthenticatedUser:
    """
    Stateless JWT verification using the shared JWT_SECRET_KEY across microservices.
    """

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Authentication credentials were not provided.',
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        user_id_str = payload.get('user_id')
        if not user_id_str:
            raise ValueError('Missing user_id claim.')

        return AuthenticatedUser(
            user_id=UUID(str(user_id_str)),
            email=str(payload.get('email', '')),
            role=str(payload.get('role', 'CUSTOMER')),
        )


    except (jwt.PyJWTError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid or expired JWT token.',
        ) from exc




def compute_webhook_signature(raw_body: bytes) -> str:
    return hmac.new(
        settings.webhook_secret.encode('utf-8'),
        raw_body,
        hashlib.sha256,
    ).hexdigest()



def verify_webhook_signature(
    raw_body: bytes,
    signature_header: str | None = Header(default=None, alias='X-Webhook-Signature'),
) -> None:
    if not signature_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Missing X-Webhook-Signature header.',
        )


    expected = compute_webhook_signature(raw_body)
    if not hmac.compare_digest(expected, signature_header.strip()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid webhook signature.',
        )


