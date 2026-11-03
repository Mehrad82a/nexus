from typing import Optional
from uuid import UUID
from accounts.models import User



def get_active_user_by_id(*, user_id: UUID) -> Optional[User]:
    """
    Retrieve an active user by their UUID primary key.
    """
    return User.objects.filter(id=user_id, is_active=True).first()



def get_user_by_email(*, email: str) -> Optional[User]:
    """
    Retrieve a user by their normalized email address.
    """
    return User.objects.filter(email__iexact=email.strip()).first()



