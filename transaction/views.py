
import uuid
from datetime import timedelta

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db import transaction as db_transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import AccountOrder
from products import cart
from products.models import Product

from .forms import OrderShippingForm, PaymentMethodForm, ShippingAddressForm
from .models import ProductReservation, TransactionOrderState


# =========================================================
# HELPER
# =========================================================

def get_order_state(order):
    legacy_status = {
        AccountOrder.Status.IN_TRANSIT: TransactionOrderState.Status.IN_TRANSIT,
        AccountOrder.Status.COMPLETED: TransactionOrderState.Status.COMPLETED,
    }.get(order.status, TransactionOrderState.Status.ACTIVE)
    state, _ = TransactionOrderState.objects.get_or_create(
        order=order, defaults={'status': legacy_status},
    )
    return state


def release_order_reservation(order):
    # Only release the reservation belonging to this order, never a newer buyer's.
    reservation = ProductReservation.objects.filter(order=order).first()
    if reservation is None:
        return
    product = Product.objects.select_for_update().filter(pk=reservation.product_id).first()
    if product is not None and product.status == Product.Status.SOLD:
        product.status = Product.Status.AVAILABLE
        product.save(update_fields=['status'])
    reservation.delete()


def expire_reservations():
    expired_ids = list(ProductReservation.objects.filter(
        expires_at__lte=timezone.now()
    ).values_list('order_id', flat=True))
    for order_id in expired_ids:
        with db_transaction.atomic():
            order = AccountOrder.objects.select_for_update().filter(pk=order_id).first()
            if order is None:
                continue
            reservation = ProductReservation.objects.filter(order=order).first()
            if reservation is None or not reservation.is_expired:
                continue
            state = get_order_state(order)
            if state.status == TransactionOrderState.Status.ACTIVE and order.status == AccountOrder.Status.AWAITING_PAYMENT:
                state.status = TransactionOrderState.Status.EXPIRED
                state.save(update_fields=['status', 'updated_at'])
                release_order_reservation(order)
            elif state.status in (TransactionOrderState.Status.CANCELLED, TransactionOrderState.Status.EXPIRED):
                release_order_reservation(order)


# =========================================================
# CHECKOUT
# =========================================================

@login_required
def checkout(request):
    expire_reservations()

    cart_items = cart.items(request.session)

    if not cart_items:
        messages.info(request, "Your bag is empty.")
        return redirect("products:home")

    product_ids = [
        item["product"].pk for item in cart_items
    ]

    if (
        any(item["quantity"] != 1 for item in cart_items)
        or len(product_ids) != len(set(product_ids))
    ):
        messages.error(
            request,
            "Each thrift product can only be purchased once."
        )
        return redirect("products:home")

    if any(
        not item["product"].is_purchasable
        for item in cart_items
    ):
        messages.warning(
            request,
            "Some items in your bag are no longer available."
        )
        return redirect("products:home")

    request.session.pop(
        "transaction_completed_orders",
        None,
    )

    if request.method == "POST":
        address_form = ShippingAddressForm(request.POST)

        if address_form.is_valid():
            request.session["transaction_address"] = (
                address_form.cleaned_data
            )
            request.session.modified = True

            return redirect("transaction:shipping")

    else:
        address_form = ShippingAddressForm(
            initial=request.session.get(
                "transaction_address", {}
            )
        )

    return render(
        request,
        "transaction/checkout.html",
        {
            "cart_items": cart_items,
            "subtotal": cart.subtotal(request.session),
            "address_form": address_form,
        },
    )


# =========================================================
# SHIPPING
# =========================================================

@login_required
def shipping(request):
    saved_address = request.session.get(
        "transaction_address", {}
    )

    if request.method == "POST":
        address_form = ShippingAddressForm(request.POST)

        if address_form.is_valid():
            request.session["transaction_address"] = (
                address_form.cleaned_data
            )
            request.session.modified = True

            messages.success(
                request,
                "Shipping address updated successfully."
            )

            return redirect("transaction:payment")

    else:
        address_form = ShippingAddressForm(
            initial=saved_address
        )

    return render(
        request,
        "transaction/shipping.html",
        {
            "address_form": address_form,
            "address": saved_address,
        },
    )


# =========================================================
# PAYMENT METHOD
# =========================================================

@login_required
def payment(request):
    if not request.session.get("transaction_address"):
        messages.info(
            request,
            "Please enter your shipping address first."
        )
        return redirect("transaction:checkout")

    if not cart.items(request.session):
        messages.info(request, "Your bag is empty.")
        return redirect("products:home")

    if request.method == "POST":
        payment_form = PaymentMethodForm(request.POST)

        if payment_form.is_valid():
            request.session["transaction_payment"] = (
                payment_form.cleaned_data["payment_method"]
            )
            request.session.modified = True

            return redirect("transaction:confirmation")

    else:
        payment_form = PaymentMethodForm(
            initial={
                "payment_method": request.session.get(
                    "transaction_payment", ""
                )
            }
        )

    return render(
        request,
        "transaction/payment.html",
        {
            "payment_form": payment_form,
            "subtotal": cart.subtotal(request.session),
        },
    )


# =========================================================
# ORDER CONFIRMATION / CREATE ORDER
# =========================================================

@login_required
def confirmation(request):
    completed_ids = request.session.get(
        "transaction_completed_orders"
    )

    if completed_ids:
        orders = AccountOrder.objects.filter(
            user=request.user,
            pk__in=completed_ids,
        ).select_related(
            "transaction_state"
        ).order_by("pk")

        return render(
            request,
            "transaction/confirmation.html",
            {
                "orders": orders,
                "completed": True,
            },
        )

    address = request.session.get("transaction_address")
    payment_method = request.session.get("transaction_payment")
    cart_items = cart.items(request.session)

    if not address or not payment_method or not cart_items:
        messages.info(
            request,
            "Please complete checkout first."
        )
        return redirect("transaction:checkout")

    if request.method == "POST":
        created_orders = []

        product_ids = [
            item["product"].pk for item in cart_items
        ]

        if (
            any(item["quantity"] != 1 for item in cart_items)
            or len(product_ids) != len(set(product_ids))
        ):
            messages.error(
                request,
                "Each thrift product can only be purchased once."
            )
            return redirect("transaction:checkout")

        try:
            with db_transaction.atomic():
                products = {
                    product.pk: product
                    for product in Product.objects.select_for_update().filter(
                        pk__in=product_ids
                    )
                }

                # Validasi seluruh produk terlebih dahulu.
                for item in cart_items:
                    product = products.get(item["product"].pk)

                    if not product or not product.is_purchasable:
                        messages.error(
                            request,
                            "A product is no longer available. "
                            "Please review your bag."
                        )
                        return redirect("transaction:checkout")

                    reservation = ProductReservation.objects.filter(
                        product=product
                    ).first()

                    if reservation and not reservation.is_expired:
                        messages.error(
                            request,
                            "A product in your bag is currently reserved."
                        )
                        return redirect("transaction:checkout")

                # Hapus reservasi lama yang sudah kedaluwarsa.
                ProductReservation.objects.filter(
                    product_id__in=product_ids,
                    expires_at__lte=timezone.now(),
                ).delete()

                batch = uuid.uuid4().hex[:10].upper()

                payment_labels = dict(
                    PaymentMethodForm.PAYMENT_CHOICES
                )

                for index, item in enumerate(
                    cart_items, start=1
                ):
                    product = products[item["product"].pk]
                    image = product.primary_image

                    order = AccountOrder.objects.create(
                        user=request.user,
                        product=product,
                        seller=product.seller,
                        number=f"G-{batch}-{index:02d}",
                        date=timezone.localdate(),
                        status=AccountOrder.Status.AWAITING_PAYMENT,
                        title=product.title,
                        condition=product.get_condition_display(),
                        image=image.image.url if image else "",
                        subtotal=item["line_total"],
                        shipping=0,
                        recipient=address["recipient"],
                        phone=address["phone"],
                        address=(
                            f'{address["address"]}, '
                            f'{address["city"]}, '
                            f'{address["postal_code"]}, '
                            f'{address["country"]}'
                        ),
                        payment_method=payment_labels[payment_method],
                    )

                    TransactionOrderState.objects.create(
                        order=order,
                        status=TransactionOrderState.Status.ACTIVE,
                    )

                    ProductReservation.objects.create(
                        product=product,
                        order=order,
                        expires_at=(
                            timezone.now() + timedelta(minutes=15)
                        ),
                    )
                    product.status = Product.Status.SOLD
                    product.save()

                    created_orders.append(order)

        except IntegrityError:
            raise

        request.session.pop("bag", None)

        request.session["transaction_completed_orders"] = [
            order.pk for order in created_orders
        ]
        request.session.modified = True

        return redirect("transaction:confirmation")

    return render(
        request,
        "transaction/confirmation.html",
        {
            "cart_items": cart_items,
            "subtotal": cart.subtotal(request.session),
            "address": address,
            "payment_method": dict(
                PaymentMethodForm.PAYMENT_CHOICES
            ).get(payment_method, payment_method),
            "completed": False,
        },
    )


@login_required
@require_POST
def place_order(request):
    return redirect("transaction:confirmation")



@login_required
@require_POST
def cancel_order(request, order_id):
    with db_transaction.atomic():
        order = get_object_or_404(
            AccountOrder.objects.select_for_update(),
            pk=order_id,
            user=request.user,
        )

        state = get_order_state(order)

        if state.status != TransactionOrderState.Status.ACTIVE:
            messages.warning(
                request,
                "This order is no longer active."
            )
            return redirect("order_detail", pk=order.pk)

        if order.status != AccountOrder.Status.AWAITING_PAYMENT:
            messages.warning(
                request,
                "Only orders awaiting payment can be cancelled."
            )
            return redirect("order_detail", pk=order.pk)

        reservation = ProductReservation.objects.filter(order=order).first()
        if reservation is not None and reservation.is_expired:
            state.status = TransactionOrderState.Status.EXPIRED
            state.save(update_fields=['status', 'updated_at'])
            release_order_reservation(order)
            messages.warning(request, 'Payment period has expired.')
            return redirect('order_detail', pk=order.pk)

        state.status = TransactionOrderState.Status.CANCELLED
        state.save(update_fields=['status', 'updated_at'])
        release_order_reservation(order)

    messages.success(
        request,
        "Your order has been cancelled."
    )

    return redirect("order_detail", pk=order.pk)


@staff_member_required
@require_POST
def confirm_payment(request, order_id):
    with db_transaction.atomic():
        order = get_object_or_404(
            AccountOrder.objects.select_for_update(),
            pk=order_id,
        )

        state = get_order_state(order)

        if (
            order.status != AccountOrder.Status.AWAITING_PAYMENT
            or state.status != TransactionOrderState.Status.ACTIVE
        ):
            messages.error(
                request,
                "Order cannot be marked as paid."
            )
            return redirect("order_detail", pk=order.pk)

        reservation = ProductReservation.objects.filter(
            order=order
        ).first()

        if not reservation or reservation.is_expired:
            state.status = TransactionOrderState.Status.EXPIRED
            state.save()

            release_order_reservation(order)

            messages.error(
                request,
                "Payment period has expired."
            )
            return redirect("order_detail", pk=order.pk)

        state.status = TransactionOrderState.Status.PAID
        state.save()

    messages.success(request, "Payment confirmed.")

    return redirect("order_detail", pk=order.pk)


@staff_member_required
@require_POST
def ship_order(request, order_id):
    with db_transaction.atomic():
        order = get_object_or_404(
            AccountOrder.objects.select_for_update(),
            pk=order_id,
        )

        state = get_order_state(order)

        if state.status != TransactionOrderState.Status.PAID:
            messages.error(
                request,
                "Order has not been paid."
            )
            return redirect("order_detail", pk=order.pk)

        shipping_form = OrderShippingForm(request.POST)
        if not shipping_form.is_valid():
            messages.error(request, 'Enter a courier and tracking number before marking this order as shipped.')
            return redirect('order_detail', pk=order.pk)
        order.courier = shipping_form.cleaned_data['courier']
        order.tracking_number = shipping_form.cleaned_data['tracking_number']
        order.status = AccountOrder.Status.IN_TRANSIT
        order.save(update_fields=['courier', 'tracking_number', 'status'])

        state.status = TransactionOrderState.Status.IN_TRANSIT
        state.save()

    messages.success(request, "Order marked as shipped.")

    return redirect("order_detail", pk=order.pk)


@login_required
@require_POST
def complete_order(request, order_id):
    with db_transaction.atomic():
        order = get_object_or_404(
            AccountOrder.objects.select_for_update(),
            pk=order_id,
            user=request.user,
        )

        state = get_order_state(order)

        if (
            order.status != AccountOrder.Status.IN_TRANSIT
            or state.status != TransactionOrderState.Status.IN_TRANSIT
        ):
            messages.error(
                request,
                "Order cannot be completed yet."
            )
            return redirect("order_detail", pk=order.pk)

        order.status = AccountOrder.Status.COMPLETED
        order.save(update_fields=["status"])

        state.status = TransactionOrderState.Status.COMPLETED
        state.save()

    messages.success(
        request,
        "Order completed. You can now submit a review."
    )

    return redirect("order_detail", pk=order.pk)
