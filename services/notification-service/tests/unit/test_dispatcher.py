import pytest

from app.services.dispatcher import DefaultNotificationDispatcher
from app.services.exceptions import InvalidEventError




def test_send_returns_dispatched_payload_for_valid_inputs() -> None:
    dispatcher = DefaultNotificationDispatcher()

    result = dispatcher.send(
        user_id='user-123',
        order_id='order-456',
        channel_type='EMAIL_AND_SMS',
        subject='Order Confirmed',
        message='Your order was paid.',
    )

    assert result == {
        'user_id': 'user-123',
        'order_id': 'order-456',
        'channel': 'EMAIL_AND_SMS',
        'subject': 'Order Confirmed',
        'status': 'sent',
    }



@pytest.mark.parametrize(
    ('user_id', 'order_id'),
    [
        ('', 'order-456'),
        ('   ', 'order-456'),
        ('user-123', ''),
        ('user-123', '   '),
    ],
)
def test_send_rejects_blank_identifiers(user_id: str, order_id: str) -> None:
    dispatcher = DefaultNotificationDispatcher()

    with pytest.raises(InvalidEventError, match='must not be blank'):
        dispatcher.send(
            user_id=user_id,
            order_id=order_id,
            channel_type='EMAIL',
            subject='Subject',
            message='Body',
        )

