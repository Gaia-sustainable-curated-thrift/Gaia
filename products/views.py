from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.db import transaction
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from accounts.models import WishlistItem
from . import cart
from .forms import ProductListingForm
from .models import Category, Product, ProductImage

CATEGORY_ORDER = {'tops': 0, 'bottoms': 1, 'bags': 2, 'shoes': 3}
GENDER_ORDER = ['women', 'men']
CONDITION_LABELS = {'signs_of_wear': 'Signs of Wear'}


def order_categories(categories):
    return sorted(categories, key=lambda c: (CATEGORY_ORDER.get(c.name.lower(), 99), c.name))


def department_categories(parent, slug):
    existing = {category.name.lower(): category for category in parent.children.all()} if parent and parent.pk else {}
    return [
        existing.get(name.lower()) or Category(name=name, slug=f'{slug}-{name.lower()}')
        for name in ['Tops', 'Bottoms', 'Shoes', 'Bags']
    ]


def home(request):
    picked = (
        Product.objects
        .filter(status=Product.Status.AVAILABLE)
        .select_related('category')
        .prefetch_related('images')
        .order_by('-created_at')[:5]
    )
    stored_parents = {parent.slug: parent for parent in Category.objects.filter(parent__isnull=True)}
    parents = [
        stored_parents.get(slug) or Category(name=slug.capitalize(), slug=slug)
        for slug in GENDER_ORDER
    ]
    gender = request.GET.get('gender', 'women')
    active_parent = next((p for p in parents if p.slug == gender), None) or (parents[0] if parents else None)
    gender_tabs = [
        {
            'parent': parent,
            'categories': department_categories(parent, parent.slug),
            'active': parent == active_parent,
        }
        for parent in parents
    ]
    return render(request, 'products/home.html', {
        'picked': picked,
        'active_parent': active_parent,
        'gender_tabs': gender_tabs,
    })


def listing(request, gender=None):
    parents = Category.objects.filter(parent__isnull=True)
    category_slug = request.GET.get('category')

    if gender:
        if gender not in GENDER_ORDER:
            raise Http404('Unknown department')
        parent = parents.filter(slug=gender).first()
        department_name = gender.capitalize()
        page_title = f"Shop {department_name}'s"
        crumb = department_name
        link_base = reverse('products:listing', args=[gender])
        products = (
            Product.objects
            .select_related('category')
            .prefetch_related('images')
            .filter(category__parent=parent, status=Product.Status.AVAILABLE) if parent else Product.objects.none()
        )
    else:
        parent = parents.first()
        page_title = "Picked For You"
        crumb = "Picked For You"
        link_base = reverse('products:picked')
        products = (
            Product.objects
            .filter(status=Product.Status.AVAILABLE)
            .select_related('category')
            .prefetch_related('images')
        )

    categories = department_categories(parent, gender or (parent.slug if parent else 'all'))

    if category_slug:
        active_category = next((c for c in categories if c.slug == category_slug or c.name.lower() == category_slug.lower()), None)
    else:
        active_category = categories[0] if categories else None

    products = products.order_by('-created_at')[:60]

    return render(request, 'products/listing.html', {
        'page_title': page_title,
        'crumb': crumb,
        'parents': parents,
        'categories': categories,
        'active_category': active_category,
        'has_active_products': any(
            product.category and active_category and product.category.name == active_category.name
            for product in products
        ),
        'products': products,
        'link_base': link_base,
    })


def search(request):
    q = request.GET.get('q', '').strip()
    if not q:
        request.session['bag_toast'] = {'kind': 'error', 'text': 'Enter a search term.'}
        return redirect('products:home')
    base = (
        Product.objects
        .filter(status=Product.Status.AVAILABLE)
        .select_related('category', 'category__parent')
        .prefetch_related('images')
    )
    base = base.filter(
        Q(title__icontains=q)
        | Q(description__icontains=q)
        | Q(style_tags__icontains=q)
        | Q(category__name__icontains=q)
        | Q(category__parent__name__icontains=q)
    )

    price_from = request.GET.get('price_from', '').strip()
    price_to = request.GET.get('price_to', '').strip()
    selected_genders = request.GET.getlist('gender')
    selected_categories = request.GET.getlist('category')
    selected_conditions = request.GET.getlist('condition')

    products = base
    if price_from.isascii() and price_from.isdigit():
        products = products.filter(price__gte=int(price_from))
    if price_to.isascii() and price_to.isdigit():
        products = products.filter(price__lte=int(price_to))
    if selected_genders:
        products = products.filter(category__parent__slug__in=selected_genders)
    if selected_categories:
        products = products.filter(category__name__in=selected_categories)
    if selected_conditions:
        products = products.filter(condition__in=selected_conditions)

    products = products.order_by('-created_at')
    result_count = products.count()
    products = products[:60]

    genders = [
        {
            'slug': parent.slug,
            'name': f"{parent.name}\u2019s",
            'count': base.filter(category__parent=parent).count(),
            'checked': parent.slug in selected_genders,
        }
        for parent in sorted(
            Category.objects.filter(parent__isnull=True),
            key=lambda p: (GENDER_ORDER.index(p.slug) if p.slug in GENDER_ORDER else 99, p.name),
        )
    ]

    category_facets = []
    seen_category_names = set()
    for category in order_categories(Category.objects.filter(parent__isnull=False)):
        if category.name in seen_category_names:
            continue
        seen_category_names.add(category.name)
        category_facets.append({
            'name': category.name,
            'count': base.filter(category__name=category.name).count(),
            'checked': category.name in selected_categories,
        })

    conditions = [
        {
            'value': value,
            'label': CONDITION_LABELS.get(value, label),
            'count': base.filter(condition=value).count(),
            'checked': value in selected_conditions,
        }
        for value, label in Product.Condition.choices
    ]

    return render(request, 'products/search.html', {
        'q': q,
        'products': products,
        'result_count': result_count,
        'price_from': price_from,
        'price_to': price_to,
        'genders': genders,
        'category_facets': category_facets,
        'conditions': conditions,
    })


def detail(request, slug):
    product = get_object_or_404(
        Product.objects
        .select_related('category', 'category__parent', 'seller', 'seller__profile')
        .prefetch_related('images'),
        slug=slug,
    )
    # Sold listings leave the shop, but their owner can still open, edit or delete them.
    if not product.is_purchasable and product.seller_id != request.user.pk:
        raise Http404('Listing is no longer available')

    images = list(product.images.all())
    primary = product.primary_image
    if primary in images:
        images.remove(primary)
        images.insert(0, primary)

    related = (
        Product.objects
        .filter(status=Product.Status.AVAILABLE)
        .select_related('category')
        .prefetch_related('images')
        .exclude(pk=product.pk)
    )
    if product.category_id:
        same_category = related.filter(category=product.category)
        if same_category.exists():
            related = same_category
    related = related.order_by('-created_at')[:5]

    saved_items = WishlistItem.objects.filter(product_key=product.slug, removed=False)
    return render(request, 'products/detail.html', {
        'product': product,
        'images': images,
        'related': related,
        'saved_count': saved_items.count(),
        'wishlist_saved': request.user.is_authenticated and saved_items.filter(user=request.user).exists(),
    })


def _seller_parents():
    return list(Category.objects.filter(parent__isnull=True).prefetch_related('children').order_by('name'))


def _listing_form_page(request, product=None):
    editing = product is not None
    existing_images = list(product.images.all()) if editing else []
    form = ProductListingForm(
        request.POST if request.method == 'POST' else None,
        request.FILES if request.method == 'POST' else None,
        instance=product,
    )
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            product = form.save(commit=False)
            product.seller = request.user
            product.save()
            next_order = max((image.order for image in existing_images), default=-1) + 1
            for index, photo in enumerate(form.cleaned_data['photos']):
                ProductImage.objects.create(
                    product=product, image=photo,
                    is_primary=not existing_images and index == 0, order=next_order + index,
                )
        message = 'Listing updated.' if editing else 'Listing created.'
        if editing or _is_ajax(request):
            request.session['bag_toast'] = {'kind': 'added', 'text': message}
        destination = _product_url(product)
        if _is_ajax(request):
            return JsonResponse({
                'ok': True,
                'product_id': product.pk,
                'redirect_url': destination,
                'message': message,
            }, status=200 if editing else 201)
        return redirect(destination)

    if request.method == 'POST' and _is_ajax(request):
        return JsonResponse({
            'ok': False,
            'errors': {field: list(messages) for field, messages in form.errors.items()},
        }, status=400)

    selected_category = form.cleaned_data.get('category') if form.is_bound else (product.category if editing else None)
    cover = product.primary_image if editing else None
    return render(request, 'products/sell.html', {
        'parents': _seller_parents(),
        'conditions': [{'value': value, 'label': label} for value, label in Product.Condition.choices],
        'form': form,
        'errors': [message for messages in form.errors.values() for message in messages],
        'selected_category': selected_category,
        'selected_parent': selected_category.parent.slug if selected_category else '',
        'editing': editing,
        'product': product,
        'existing_images': existing_images,
        'cover_id': cover.pk if cover else None,
    })


@login_required
def sell(request):
    return _listing_form_page(request)


@login_required
def edit(request, slug):
    product = get_object_or_404(
        Product.objects.select_related('category__parent').prefetch_related('images'),
        slug=slug, seller=request.user,
    )
    return _listing_form_page(request, product)


@login_required
@require_POST
def delete_listing(request, slug):
    product = get_object_or_404(Product, slug=slug, seller=request.user)
    product_id = product.pk
    product.delete()
    cart.remove(request.session, product_id)
    if request.session.get('bag_undo', {}).get('product_id') == product_id:
        request.session.pop('bag_undo')
    request.session['bag_toast'] = {'kind': 'added', 'text': 'Listing deleted.'}
    return _redirect_back(request, reverse('products:home'))


def _product_url(product):
    return reverse('products:detail', args=[product.slug])


def _redirect_back(request, fallback):
    target = request.POST.get('next') or request.GET.get('next')
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(target)
    return redirect(fallback)


def _is_ajax(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _bag_json(request, *, toast=None, open_drawer=False, status=200):
    items = cart.items(request.session)
    context = {
        'bag_items': items,
        'bag_count': sum(item['quantity'] for item in items),
        'bag_subtotal': sum(item['line_total'] for item in items),
        'bag_toast': toast,
        'bag_open': open_drawer,
    }
    return JsonResponse({
        'ok': status < 400,
        'bag_count': context['bag_count'],
        'bag_slugs': [item['product'].slug for item in items],
        'drawer': render_to_string('includes/bag_drawer_body.html', context, request=request),
        'toast': toast if toast and toast.get('kind') in ('added', 'error') else None,
        'open': open_drawer,
    }, status=status)


def _is_own_listing(request, product):
    return request.user.is_authenticated and product.seller_id == request.user.pk


def _bag_error(request, text, fallback, *, open_drawer=False, status=409):
    toast = {'kind': 'error', 'text': text}
    if _is_ajax(request):
        return _bag_json(request, toast=toast, open_drawer=open_drawer, status=status)
    request.session['bag_toast'] = toast
    request.session['bag_open'] = open_drawer
    return redirect(fallback)


@require_POST
def bag_add(request, slug):
    product = get_object_or_404(Product, slug=slug)
    if not product.is_purchasable:
        return _bag_error(request, 'This item is no longer available.', reverse('products:home'))
    if _is_own_listing(request, product):
        return _bag_error(request, 'You cannot buy your own listing.', _product_url(product), status=403)
    already_in_bag = cart.quantity_for(request.session, product.pk) > 0
    cart.add(request.session, product.pk)
    toast = {
        'kind': 'added',
        'text': 'This item is already in your bag.' if already_in_bag else f'Added \u201c{product.title}\u201d to bag',
        'icon': True,
    }
    if _is_ajax(request):
        return _bag_json(request, toast=toast)
    request.session['bag_toast'] = toast
    return _redirect_back(request, _product_url(product))


@require_POST
def bag_remove(request, slug):
    product = get_object_or_404(Product, slug=slug)
    in_bag = cart.quantity_for(request.session, product.pk) > 0
    cart.remove(request.session, product.pk)
    toast = {
        'kind': 'added',
        'text': f'Removed \u201c{product.title}\u201d from bag' if in_bag else 'This item is not in your bag.',
        'icon': True,
    }
    if _is_ajax(request):
        return _bag_json(request, toast=toast)
    request.session['bag_toast'] = toast
    return _redirect_back(request, _product_url(product) if product.is_purchasable else reverse('products:home'))


@require_POST
def bag_set(request, slug):
    product = get_object_or_404(Product, slug=slug)
    try:
        quantity = int(request.POST.get('quantity', ''))
    except (TypeError, ValueError):
        return _bag_error(
            request, 'Enter a valid whole-number quantity.', _product_url(product) if product.is_purchasable else reverse('products:home'),
            open_drawer=True, status=400,
        )

    if quantity > 0 and not product.is_purchasable:
        return _bag_error(
            request, 'This item is no longer available.',
            reverse('products:home'), open_drawer=True,
        )
    if quantity > 0 and _is_own_listing(request, product):
        return _bag_error(request, 'You cannot buy your own listing.', _product_url(product), open_drawer=True, status=403)
    if quantity > cart.MAX_QUANTITY:
        return _bag_error(request, 'Each listing is available only once.', _product_url(product), open_drawer=True, status=400)

    toast = None
    if quantity <= 0:
        previous = cart.quantity_for(request.session, product.pk)
        cart.remove(request.session, product.pk)
        if previous:
            request.session['bag_undo'] = {'product_id': product.pk, 'quantity': previous}
            toast = {'kind': 'removed', 'text': 'Item removed', 'undo': True}
    else:
        cart.set_quantity(request.session, product.pk, quantity)

    if _is_ajax(request):
        return _bag_json(request, toast=toast, open_drawer=True)
    request.session['bag_toast'] = toast
    request.session['bag_open'] = True
    return _redirect_back(request, _product_url(product)) if product.is_purchasable else redirect('products:home')


@require_POST
def bag_undo(request):
    entry = request.session.pop('bag_undo', None)
    toast = None
    if entry:
        product = Product.objects.filter(pk=entry['product_id']).first()
        if product is None or not product.is_purchasable or _is_own_listing(request, product):
            return _bag_error(
                request, 'This item is no longer available and could not be restored.',
                reverse('products:home'), open_drawer=True,
            )
        cart.set_quantity(request.session, product.pk, entry.get('quantity', 1))
        toast = {'kind': 'added', 'text': 'Item added back to bag', 'icon': True}
    if _is_ajax(request):
        return _bag_json(request, toast=toast, open_drawer=True)
    request.session['bag_toast'] = toast
    request.session['bag_open'] = True
    return _redirect_back(request, reverse('products:home'))


def _wish_login_required(request, product):
    login_response = redirect_to_login(_product_url(product), settings.LOGIN_URL)
    if _is_ajax(request):
        return JsonResponse({'ok': False, 'login_url': login_response.url}, status=401)
    return login_response


def _wish_response(request, product, *, saved, toast):
    if _is_ajax(request):
        return JsonResponse({
            'ok': True,
            'saved': saved,
            'toast': toast,
            'saved_count': WishlistItem.objects.filter(product_key=product.slug, removed=False).count(),
        })
    request.session['bag_toast'] = toast
    return _redirect_back(request, _product_url(product))


@require_POST
def wish_add(request, slug):
    product = get_object_or_404(Product, slug=slug, status=Product.Status.AVAILABLE)
    if not request.user.is_authenticated:
        return _wish_login_required(request, product)
    if _is_own_listing(request, product):
        toast = {'kind': 'error', 'text': 'You cannot save your own listing.'}
        if _is_ajax(request):
            return JsonResponse({'ok': False, 'toast': toast}, status=403)
        request.session['bag_toast'] = toast
        return redirect(_product_url(product))

    image = product.primary_image
    WishlistItem.objects.update_or_create(
        user=request.user,
        product_key=product.slug,
        defaults={
            'title': product.title,
            'condition': product.get_condition_display(),
            'price': product.price,
            'image': image.image.url if image else '',
            'removed': False,
        },
    )
    toast = {
        'kind': 'added',
        'text': f'Saved \u201c{product.title}\u201d to wishlist',
        'icon': 'heart',
    }
    return _wish_response(request, product, saved=True, toast=toast)


@require_POST
def wish_remove(request, slug):
    product = get_object_or_404(Product, slug=slug, status=Product.Status.AVAILABLE)
    if not request.user.is_authenticated:
        return _wish_login_required(request, product)

    WishlistItem.objects.filter(user=request.user, product_key=product.slug, removed=False).update(removed=True)
    toast = {
        'kind': 'added',
        'text': f'Removed \u201c{product.title}\u201d from wishlist',
        'icon': 'heart',
    }
    return _wish_response(request, product, saved=False, toast=toast)
