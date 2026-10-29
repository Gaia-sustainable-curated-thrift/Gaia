
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction as db_transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import AccountOrder
from products import cart
from products.models import Product
from .forms import PaymentMethodForm, ShippingAddressForm


@login_required
def checkout(request):
    cart_items = cart.items(request.session)

    if not cart_items:
        messages.info(request, "Your bag is empty.")
        return redirect("products:home")

    if any(not item["product"].is_purchasable for item in cart_items):
        messages.warning(
            request,
            "Some items in your bag are no longer available."
        )
        return redirect("products:home")

    # Mulai checkout baru.
    request.session.pop("transaction_completed_orders", None)

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
            initial=request.session.get("transaction_address", {})
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


@login_required
def shipping(request):
    # Ambil alamat yang sebelumnya disimpan di session.
    saved_address = request.session.get("transaction_address", {})

    if request.method == "POST":
        address_form = ShippingAddressForm(request.POST)

        if address_form.is_valid():
            # Simpan alamat yang sudah diperbarui.
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
        # Isi form dengan alamat sebelumnya agar bisa diedit.
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


@login_required
def confirmation(request):
    # Jika pesanan sudah dibuat, refresh tidak membuat pesanan baru.
    completed_ids = request.session.get(
        "transaction_completed_orders"
    )

    if completed_ids:
        orders = AccountOrder.objects.filter(
            user=request.user,
            pk__in=completed_ids,
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

        # Ambil ulang produk dari database dan kunci record
        # selama proses validasi dan pembuatan pesanan.
        product_ids = [
            item["product"].pk for item in cart_items
        ]

        with db_transaction.atomic():
            products = {
                product.pk: product
                for product in Product.objects.select_for_update().filter(
                    pk__in=product_ids
                )
            }

            # Pastikan semua produk masih tersedia.
            for item in cart_items:
                product = products.get(item["product"].pk)

                if not product or not product.is_purchasable:
                    messages.error(
                        request,
                        "A product is no longer available. "
                        "Please review your bag."
                    )
                    return redirect("transaction:checkout")

            batch = uuid.uuid4().hex[:10].upper()
            payment_labels = dict(
                PaymentMethodForm.PAYMENT_CHOICES
            )

            # Setiap produk mendapatkan nomor pesanan tersendiri.
            for index, item in enumerate(cart_items, start=1):
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
                    subtotal=product.price * item["quantity"],
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

                created_orders.append(order)

        # Kosongkan keranjang setelah semua pesanan berhasil dibuat.
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
    # Form konfirmasi dikirim ke view confirmation.
    return redirect("transaction:confirmation")


