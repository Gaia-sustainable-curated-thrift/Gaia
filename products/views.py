from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from .models import Category, Product

CATEGORY_ORDER = {'tops': 0, 'bottoms': 1, 'bags': 2, 'shoes': 3}


def order_categories(categories):
    return sorted(categories, key=lambda c: (CATEGORY_ORDER.get(c.name.lower(), 99), c.name))


def home(request):
    picked = (
        Product.objects
        .select_related('category')
        .prefetch_related('images')
        .order_by('-created_at')[:10]
    )
    parents = Category.objects.filter(parent__isnull=True)
    gender = request.GET.get('gender', 'women')
    active_parent = parents.filter(slug=gender).first() or parents.first()
    categories = order_categories(active_parent.children.all()) if active_parent else []
    return render(request, 'products/home.html', {
        'picked': picked,
        'parents': parents,
        'active_parent': active_parent,
        'categories': categories,
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

    if active_category:
        products = products.filter(category=active_category)

    products = products.order_by('-created_at')[:20]

    return render(request, 'products/listing.html', {
        'page_title': page_title,
        'crumb': crumb,
        'parents': parents,
        'categories': categories,
        'active_category': active_category,
        'products': products,
        'link_base': link_base,
    })
