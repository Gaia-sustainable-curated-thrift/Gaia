def basket_count(request):
    if request.user.is_authenticated:
        return {'basket_count': request.user.basket_items.count()}
    return {'basket_count': 0}