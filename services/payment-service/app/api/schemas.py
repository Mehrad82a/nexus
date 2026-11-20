from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field




class PaymentCreateRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    order_id: UUID
    idempotency_key: str = Field(min_length=1, max_length=120)
    amount: Decimal = Field(gt=Decimal('0.00'), max_digits=12, decimal_places=2)
    currency: str = Field(default='USD', max_length=10)
    simulate_failure: bool = Field(default=False, description='If True, simulates a declined card for testing Saga rollback.')




class PaymentWebhookRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    order_id: UUID
    provider_tx_id: str = Field(min_length=1, max_length=120)
    event_status: Literal['SUCCEEDED', 'FAILED']
    failure_reason: str | None = None


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    user_id: UUID
    idempotency_key: str
    amount: Decimal
    currency: str
    provider: str
    provider_tx_id: str | None
    status: str
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime
