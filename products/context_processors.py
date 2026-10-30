from . import cart


def basket(request):
    items = cart.items(request.session)
    return {
        'bag_items': items,
        'bag_count': sum(item['quantity'] for item in items),
        'bag_slugs': {item['product'].slug for item in items},
        'bag_subtotal': sum(item['line_total'] for item in items),
        'bag_toast': request.session.pop('bag_toast', None),
        'bag_open': request.session.pop('bag_open', False),
    }