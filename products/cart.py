from django.contrib.auth import SESSION_KEY as AUTH_SESSION_KEY

from .models import Product

SESSION_KEY = 'bag'
# Each thrift listing represents one physical item.
MAX_QUANTITY = 1


def _read(session):
    data = session.get(SESSION_KEY)
    if not isinstance(data, dict):
        return {}
    cleaned = {}
    for key, quantity in data.items():
        key = str(key)
        if not key.isascii() or not key.isdecimal():
            continue
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            continue
        if quantity > 0:
            cleaned[str(int(key))] = min(quantity, MAX_QUANTITY)
    return cleaned


def _write(session, data):
    if data:
        session[SESSION_KEY] = data
    else:
        session.pop(SESSION_KEY, None)
    session.modified = True


def quantity_for(session, product_id):
    return _read(session).get(str(product_id), 0)


def add(session, product_id, quantity=1):
    data = _read(session)
    key = str(product_id)
    data[key] = min(data.get(key, 0) + max(1, int(quantity)), MAX_QUANTITY)
    _write(session, data)


def set_quantity(session, product_id, quantity):
    data = _read(session)
    key = str(product_id)
    quantity = int(quantity)
    if quantity <= 0:
        data.pop(key, None)
    else:
        data[key] = min(quantity, MAX_QUANTITY)
    _write(session, data)


def remove(session, product_id):
    data = _read(session)
    data.pop(str(product_id), None)
    _write(session, data)


def items(session):
    data = _read(session)
    if not data:
        return []
    ids = [int(key) for key in data]
    products = (
        Product.objects
        .select_related('category')
        .prefetch_related('images')
        .filter(pk__in=ids, status=Product.Status.AVAILABLE)
    )
    # A seller can never buy their own listing, even one added before signing in.
    owner_id = session.get(AUTH_SESSION_KEY)
    if owner_id is not None:
        products = products.exclude(seller_id=owner_id)
    by_id = {str(product.pk): product for product in products}
    available = {key: quantity for key, quantity in data.items() if key in by_id}
    if session.get(SESSION_KEY) != available:
        _write(session, available)
    result = []
    for key, quantity in data.items():
        product = by_id.get(key)
        if not product:
            continue
        result.append({
            'product': product,
            'quantity': quantity,
            'line_total': product.price * quantity,
        })
    return result


def count(session):
    return sum(item['quantity'] for item in items(session))


def subtotal(session):
    return sum(item['line_total'] for item in items(session))
