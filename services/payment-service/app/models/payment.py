import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import DateTime, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base



class PaymentStatus:
    PENDING = 'PENDING'
    SUCCEEDED = 'SUCCEEDED'
    FAILED = 'FAILED'
    REFUNDED = 'REFUNDED'



class Payment(Base):
    __tablename__ = 'payments'

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        unique=True,
        index=True,
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        index=True,
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(120),
        unique=True,
        index=True,
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(10),
        default='USD',
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        default='MOCK_STRIPE',
        nullable=False,
    )
    provider_tx_id: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        default=PaymentStatus.PENDING,
        index=True,
        nullable=False,
    )
    failure_reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index('idx_payments_user_status', 'user_id', 'status'),
    )

