from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment




async def get_payment_by_order_id(
    session: AsyncSession,
    *,
    order_id: UUID,
) -> Payment | None:

    stmt = select(Payment).where(Payment.order_id == order_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()



async def get_payment_by_idempotency_key(
    session: AsyncSession,
    *,
    idempotency_key: str,
) -> Payment | None:

    stmt = select(Payment).where(Payment.idempotency_key == idempotency_key)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()



