from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from accounts.models import WishlistItem
from . import cart
from .models import Category, Product, ProductImage

CATEGORY_ORDER = {'tops': 0, 'bottoms': 1, 'bags': 2, 'shoes': 3}
GENDER_ORDER = ['women', 'men']
CONDITION_LABELS = {'signs_of_wear': 'Signs of Wear'}

SAVED_COUNT = 100
SELLER_RATING = '5.0'
SELLER_REVIEWS = 120


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
            .filter(category__parent=parent) if parent else Product.objects.none()
        )
    else:
        parent = parents.first()
        page_title = "Picked For You"
        crumb = "Picked For You"
        link_base = reverse('products:picked')
        products = (
            Product.objects
            .select_related('category')
            .prefetch_related('images')
        )

    categories = department_categories(parent, gender or (parent.slug if parent else 'all'))

    if category_slug:
        active_category = next((c for c in categories if c.slug == category_slug), None)
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
    base = (
        Product.objects
        .select_related('category', 'category__parent')
        .prefetch_related('images')
    )
    if q:
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
    if price_from.isdigit():
        products = products.filter(price__gte=int(price_from))
    if price_to.isdigit():
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
        .select_related('category', 'category__parent', 'seller')
        .prefetch_related('images'),
        slug=slug,
    )

    images = list(product.images.all())
    primary = product.primary_image
    if primary in images:
        images.remove(primary)
        images.insert(0, primary)

    related = (
        Product.objects
        .select_related('category')
        .prefetch_related('images')
        .exclude(pk=product.pk)
    )
    if product.category_id:
        same_category = related.filter(category=product.category)
        if same_category.exists():
            related = same_category
    related = related.order_by('-created_at')[:5]

    return render(request, 'products/detail.html', {
        'product': product,
        'images': images,
        'related': related,
        'saved_count': SAVED_COUNT,
        'seller_rating': SELLER_RATING,
        'seller_reviews': SELLER_REVIEWS,
    })


def _seller_parents():
    return list(Category.objects.filter(parent__isnull=True).order_by('name'))


@login_required
def sell(request):
    parents = _seller_parents()
    conditions = [{'value': value, 'label': label} for value, label in Product.Condition.choices]

    if request.method == 'POST':
        errors = []
        title = request.POST.get('title', '').strip()
        category_id = request.POST.get('category')
        price_raw = request.POST.get('price', '').strip()
        description = request.POST.get('description', '').strip()
        condition = request.POST.get('condition', Product.Condition.GOOD)
        photos = request.FILES.getlist('photos')

        if not title:
            errors.append('Listing title is required.')
        if not category_id:
            errors.append('Choose a category.')

        price = None
        digits = ''.join(ch for ch in price_raw if ch.isdigit())
        if not digits:
            errors.append('Enter a price.')
        else:
            price = int(digits)

        category = None
        if category_id:
            category = Category.objects.filter(pk=category_id, parent__isnull=False).first()
            if category is None:
                errors.append('Choose a valid category.')

        if condition not in dict(Product.Condition.choices):
            condition = Product.Condition.GOOD

        if len(photos) > 5:
            errors.append('Select maximum 5 photos.')

        if not errors:
            product = Product.objects.create(
                seller=request.user,
                title=title,
                description=description,
                price=price,
                category=category,
                condition=condition,
            )
            for index, photo in enumerate(photos):
                ProductImage.objects.create(product=product, image=photo, is_primary=index == 0, order=index)
            return redirect('products:detail', slug=product.slug)

        return render(request, 'products/sell.html', {
            'parents': parents,
            'conditions': conditions,
            'errors': errors,
            'selected_parent': request.POST.get('parent', ''),
            'form': {
                'title': title,
                'category': category_id or '',
                'price': price_raw,
                'description': description,
                'condition': condition,
            },
        })

    return render(request, 'products/sell.html', {
        'parents': parents,
        'conditions': conditions,
        'selected_parent': parents[0].slug if parents else '',
    })


def _product_url(product):
    return reverse('products:detail', args=[product.slug])


def _redirect_back(request, fallback):
    target = request.POST.get('next') or request.GET.get('next')
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(target)
    return redirect(fallback)


def _is_ajax(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _bag_json(request, *, toast=None, open_drawer=False):
    items = cart.items(request.session)
    context = {
        'bag_items': items,
        'bag_count': sum(item['quantity'] for item in items),
        'bag_subtotal': sum(item['line_total'] for item in items),
        'bag_toast': toast,
        'bag_open': open_drawer,
    }
    return JsonResponse({
        'ok': True,
        'bag_count': context['bag_count'],
        'drawer': render_to_string('includes/bag_drawer_body.html', context, request=request),
        'toast': toast if toast and toast.get('kind') == 'added' else None,
        'open': open_drawer,
    })


@require_POST
def bag_add(request, slug):
    product = get_object_or_404(Product, slug=slug)
    cart.add(request.session, product.pk)
    toast = {
        'kind': 'added',
        'text': f'Added \u201c{product.title}\u201d to bag',
        'icon': True,
    }
    if _is_ajax(request):
        return _bag_json(request, toast=toast)
    request.session['bag_toast'] = toast
    return _redirect_back(request, _product_url(product))


@require_POST
def bag_set(request, slug):
    product = get_object_or_404(Product, slug=slug)
    try:
        quantity = int(request.POST.get('quantity', 1))
    except (TypeError, ValueError):
        quantity = 1

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
    return _redirect_back(request, _product_url(product))


@require_POST
def bag_undo(request):
    entry = request.session.pop('bag_undo', None)
    toast = None
    if entry:
        cart.set_quantity(request.session, entry['product_id'], entry.get('quantity', 1))
        toast = {'kind': 'added', 'text': 'Item added back to bag', 'icon': True}
    if _is_ajax(request):
        return _bag_json(request, toast=toast, open_drawer=True)
    request.session['bag_toast'] = toast
    request.session['bag_open'] = True
    return _redirect_back(request, reverse('products:home'))


@require_POST
def wish_add(request, slug):
    product = get_object_or_404(Product, slug=slug)
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)

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
    request.session['bag_toast'] = {
        'kind': 'added',
        'text': f'Saved \u201c{product.title}\u201d to wishlist',
    }
    return _redirect_back(request, _product_url(product))
