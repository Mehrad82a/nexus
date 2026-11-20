import uuid
from decimal import Decimal
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.messaging.producer.producer import EventProducer
from app.models.payment import Payment, PaymentStatus
from app.service.locks import redis_distributed_lock



class PaymentService:
    """
    Idempotent Payment Processor for both Async FastAPI endpoints and Sync RabbitMQ Saga Workers.
    """

    @staticmethod
    async def process_payment_async(
        session: AsyncSession,
        *,
        order_id: UUID,
        user_id: UUID,
        idempotency_key: str,
        amount: Decimal,
        currency: str = 'USD',
        simulate_failure: bool = False,
        producer: EventProducer | None = None,
    ) -> Payment:

        cleaned_key = idempotency_key.strip()

        with redis_distributed_lock(f'{order_id}:{cleaned_key}', ttl_seconds=15):
            stmt = select(Payment).where(
                or_(
                    Payment.idempotency_key == cleaned_key,
                    Payment.order_id == order_id,
                )
            )
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing is not None:
                return existing


            if simulate_failure:
                payment_status = PaymentStatus.FAILED
                tx_id = None
                failure_reason = 'CARD_DECLINED'
            else:
                payment_status = PaymentStatus.SUCCEEDED
                tx_id = f'ch_mock_{uuid.uuid4().hex[:16]}'
                failure_reason = None

            payment = Payment(
                order_id=order_id,
                user_id=user_id,
                idempotency_key=cleaned_key,
                amount=amount,
                currency=currency,
                provider='MOCK_STRIPE',
                provider_tx_id=tx_id,
                status=payment_status,
                failure_reason=failure_reason,
            )

            session.add(payment)
            await session.commit()
            await session.refresh(payment)

            event_producer = producer if producer is not None else EventProducer()
            if payment.status == PaymentStatus.SUCCEEDED:
                event_producer.publish(
                    event_type='payment.succeeded',
                    payload={
                        'payment_id': str(payment.id),
                        'order_id': str(payment.order_id),
                        'user_id': str(payment.user_id),
                        'amount': str(payment.amount),
                        'provider_tx_id': payment.provider_tx_id,
                    },
                )
            else:
                event_producer.publish(
                    event_type='payment.failed',
                    payload={
                        'payment_id': str(payment.id),
                        'order_id': str(payment.order_id),
                        'user_id': str(payment.user_id),
                        'reason': payment.failure_reason or 'PAYMENT_FAILED',
                    }
                )

            return payment



    @staticmethod
    def process_payment_sync(
        session: Session,
        *,
        order_id: UUID,
        user_id: UUID,
        idempotency_key: str,
        amount: Decimal,
        currency: str = "USD",
        simulate_failure: bool = False,
        producer: EventProducer |  None = None,
    ) -> Payment:
        """
        Synchronous version used by the RabbitMQ Pika consumer when 'inventory.reserved' arrives.
        """

        cleaned_key = idempotency_key.strip()

        with redis_distributed_lock(f'{order_id}:{cleaned_key}', ttl_seconds=15):
            stmt = select(Payment).where(
                or_(
                    Payment.idempotency_key == cleaned_key,
                    Payment.order_id == order_id,
                )
            )
            existing = session.execute(stmt).scalar_one_or_none()
            if existing is not None:
                return existing

            if simulate_failure:
                payment_status = PaymentStatus.FAILED
                tx_id = None
                failure_reason = 'CARD_DECLINED'

            else:
                payment_status = PaymentStatus.SUCCEEDED
                tx_id = f'ch_mock_{uuid.uuid4().hex[:16]}'
                failure_reason = None


            payment = Payment(
                order_id=order_id,
                user_id=user_id,
                idempotency_key=cleaned_key,
                amount=amount,
                currency=currency,
                provider='MOCK_STRIPE',
                provider_tx_id=tx_id,
                status=payment_status,
                failure_reason=failure_reason,
            )

            session.add(payment)
            session.commit()
            session.refresh(payment)

            event_producer = producer if producer is not None else EventProducer()
            if payment_status == PaymentStatus.SUCCEEDED:
                event_producer.publish(
                    event_type='payment.succeeded',
                    payload={
                        'payment_id': str(payment.id),
                        'order_id': str(payment.order_id),
                        'user_id': str(payment.user_id),
                        'amount': str(payment.amount),
                        'provider_tx_id': payment.provider_tx_id,
                    }
                )

            else:
                event_producer.publish(
                    event_type='payment.failed',
                    payload={
                        'payment_id': str(payment.id),
                        'order_id': str(payment.order_id),
                        'user_id': str(payment.user_id),
                        'reason': payment.failure_reason or 'PAYMENT_FAILED',
                    },
                )

            return payment



    @staticmethod
    async def handle_webhook_update(
        session: AsyncSession,
        *,
        order_id: UUID,
        provider_tx_id: str,
        event_status: str,
        failure_reason: str | None = None,
        producer: EventProducer | None = None,
    ) -> Payment:

        stmt = select(Payment).where(Payment.order_id == order_id)
        payment = (await session.execute(stmt)).scalar_one_or_none()
        if payment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Payment record for order not found.',
            )

        if payment.status == event_status:
            return payment

        payment.provider_tx_id = provider_tx_id
        payment.status = event_status
        payment.failure_reason = failure_reason
        await session.commit()
        await session.refresh(payment)

        event_producer = producer if producer is not None else EventProducer()
        if event_status == PaymentStatus.SUCCEEDED:
            event_producer.publish(
                event_type='payment.succeeded',
                payload={
                    'payment_id': str(payment.id),
                    'order_id': str(payment.order_id),
                    'user_id': str(payment.user_id),
                    'amount': str(payment.amount),
                    'provider_tx_id': payment.provider_tx_id,
                },
            )

        elif event_status == PaymentStatus.FAILED:
            event_producer.publish(
                event_type='payment.failed',
                payload={
                    'payment_id': str(payment.id),
                    'order_id': str(payment.order_id),
                    'user_id': str(payment.user_id),
                    'reason': payment.failure_reason or 'WEBHOOK_PAYMENT_FAILED',
                },
            )

        return payment

