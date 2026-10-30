"""Read-only presentation of Salma's transaction state for account pages."""
from accounts.models import AccountOrder
from transaction.models import TransactionOrderState


def order_display(order, viewer):
    state = getattr(order, 'transaction_state', None)
    reservation = getattr(order, 'product_reservation', None)
    status = state.status if state is not None else order.status
    if status == TransactionOrderState.Status.ACTIVE:
        status = order.status
    labels = {
        'awaiting_payment': 'Awaiting payment', 'paid': 'Payment confirmed',
        'in_transit': 'In transit', 'completed': 'Completed',
        'cancelled': 'Cancelled', 'expired': 'Expired',
    }
    notes = {
        'awaiting_payment': 'Payment has not been confirmed. An administrator will verify your payment.',
        'paid': 'Your payment has been verified. Your order is waiting to be shipped.',
        'in_transit': 'Your item is on its way. Confirm receipt only after it arrives.',
        'completed': 'Order completed. You can now leave a review for your seller.',
        'cancelled': 'This order was cancelled. No payment is confirmed for this order.',
        'expired': 'The payment period has ended. This order can no longer be paid.',
    }
    active = status == 'awaiting_payment'
    current_reservation = bool(reservation is not None and not reservation.is_expired)
    owner = viewer.pk == order.user_id
    staff = viewer.is_active and viewer.is_staff
    return {
        'status': status, 'label': labels.get(status, order.get_status_display()),
        'note': notes.get(status, order.status_note),
        'payment_label': 'Paid' if status in ('paid', 'in_transit', 'completed') else 'Not paid',
        'can_cancel': owner and active,
        'can_complete': owner and status == 'in_transit',
        'can_confirm_payment': staff and active and current_reservation,
        'can_ship': staff and status == 'paid',
        'expires_at': reservation.expires_at if active and current_reservation else None,
    }
