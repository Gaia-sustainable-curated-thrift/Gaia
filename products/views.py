from django.db.models import Q
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from .models import Category, Product

CATEGORY_ORDER = {'tops': 0, 'bottoms': 1, 'bags': 2, 'shoes': 3}
SIZE_ORDER = ['xs', 's', 'm', 'l', 'xl']
GENDER_ORDER = ['women', 'men']
CONDITION_LABELS = {'signs_of_wear': 'Signs of Wear'}

SAVED_COUNT = 100
SELLER_RATING = '5.0'
SELLER_REVIEWS = 120


def order_categories(categories):
    return sorted(categories, key=lambda c: (CATEGORY_ORDER.get(c.name.lower(), 99), c.name))


def home(request):
    picked = (
        Product.objects
        .select_related('category')
        .prefetch_related('images')
        .order_by('-created_at')[:10]
    )
    parents = list(Category.objects.filter(parent__isnull=True))
    gender = request.GET.get('gender', 'women')
    active_parent = next((p for p in parents if p.slug == gender), None) or (parents[0] if parents else None)
    gender_tabs = [
        {
            'parent': parent,
            'categories': order_categories(parent.children.all()),
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
        parent = get_object_or_404(Category, slug=gender, parent__isnull=True)
        page_title = f"Shop {parent.name}'s"
        crumb = parent.name
        link_base = reverse('products:listing', args=[parent.slug])
        products = (
            Product.objects
            .select_related('category')
            .prefetch_related('images')
            .filter(category__parent=parent)
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

    categories = order_categories(parent.children.all()) if parent else []

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
            | Q(brand__icontains=q)
            | Q(description__icontains=q)
            | Q(style_tags__icontains=q)
            | Q(color__icontains=q)
            | Q(category__name__icontains=q)
            | Q(category__parent__name__icontains=q)
        )

    price_from = request.GET.get('price_from', '').strip()
    price_to = request.GET.get('price_to', '').strip()
    selected_genders = request.GET.getlist('gender')
    selected_categories = request.GET.getlist('category')
    selected_sizes = request.GET.getlist('size')
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
    if selected_sizes:
        products = products.filter(size__in=selected_sizes)
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

    raw_sizes = set(base.exclude(size='').values_list('size', flat=True).distinct())
    sizes = [
        {
            'value': size,
            'count': base.filter(size=size).count(),
            'checked': size in selected_sizes,
        }
        for size in sorted(raw_sizes, key=lambda s: (SIZE_ORDER.index(s.lower()) if s.lower() in SIZE_ORDER else 99, s))
    ]

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
        'sizes': sizes,
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
