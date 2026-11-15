from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    PaymentCreateRequest,
    PaymentResponse,
    PaymentWebhookRequest,
)
from app.core.database import get_db_session
from app.core.security import (
    AuthenticatedUser,
    get_current_user,
    verify_webhook_signature,
)
from app.service.selectors import get_payment_by_order_id
from app.service.services import PaymentService




router = APIRouter(prefix='/api/v1/payments', tags=['payments'])




@router.post(
    '/process',
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def process_payment_endpoint(
    payload: PaymentCreateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    idempotency_header: str | None = Header(default=None, alias='Idempotency-Key'),
) -> PaymentResponse:

    effective_key = idempotency_header or payload.idempotency_key
    payment = await PaymentService.process_payment_async(
        session,
        order_id=payload.order_id,
        user_id=current_user.user_id,
        idempotency_key=effective_key,
        amount=payload.amount,
        currency=payload.currency,
        simulate_failure=payload.simulate_failure,
    )
    return PaymentResponse.model_validate(payment)



@router.get(
    '/order/{order_id}',
    response_model=PaymentResponse,
    status_code=status.HTTP_200_OK,
)
async def get_order_payment_endpoint(
    order_id: UUID,
    current_user: AuthenticatedUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> PaymentResponse:

    payment = await get_payment_by_order_id(session, order_id=order_id)
    if payment is None or payment.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Payment not found.',
        )

    return PaymentResponse.model_validate(payment)





@router.post(
    '/webhook',
    response_model=PaymentResponse,
    status_code=status.HTTP_200_OK,
)
async def payment_webhook_endpoint(
    request: Request,
    payload: PaymentWebhookRequest,
    session: AsyncSession = Depends(get_db_session),
    x_webhook_signature: str | None = Header(default=None, alias='X-Webhook-Signature'),
) -> PaymentResponse:

    raw_body = await request.body()
    verify_webhook_signature(raw_body=raw_body, signature_header=x_webhook_signature)

    payment = await PaymentService.handle_webhook_update(
        session,
        order_id=payload.order_id,
        provider_tx_id=payload.provider_tx_id,
        event_status=payload.event_status,
        failure_reason=payload.failure_reason,
    )
    return PaymentResponse.model_validate(payment)




