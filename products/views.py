"""Views untuk modul Product.

Urutan file ini ngikutin alur pengunjung di toko:
    1. helper kecil yang dipakai bagian-bagian di bawahnya
    2. browsing: home, halaman listing, search, dan detail produk
    3. jualan: bikin, edit, dan hapus listing (cuma pemiliknya)
    4. shopping bag (disimpan di session, jadi tamu juga bisa pakai)
    5. wishlist (harus login)

Setiap aksi yang ngubah data punya dua jenis jawaban: kalau request-nya AJAX,
balasannya JSON supaya halaman bisa update tanpa reload; kalau form biasa,
balasannya redirect plus toast.
"""
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.db import transaction
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.models import WishlistItem
from . import cart
from .decorators import owner_required, rate_limit
from .forms import ProductListingForm
from .models import Category, Product, ProductImage

# Urutan tampil departemen dan kategori di tab maupun filter, biar selalu konsisten.
GENDER_ORDER = ['women', 'men']
CATEGORY_NAMES = ['Tops', 'Bottoms', 'Shoes', 'Bags']
CATEGORY_ORDER = {'tops': 0, 'bottoms': 1, 'bags': 2, 'shoes': 3}
CONDITION_LABELS = {'signs_of_wear': 'Signs of Wear'}


# ---------------------------------------------------------------------------
# 1. Helper
# ---------------------------------------------------------------------------

def available_products():
    """Listing yang masih dijual, lengkap dengan kategori dan fotonya.

    select_related/prefetch_related dipakai supaya kategori dan foto diambil
    sekaligus, bukan satu query tambahan untuk setiap card produk.
    """
    return (
        Product.objects
        .filter(status=Product.Status.AVAILABLE)
        .select_related('category')
        .prefetch_related('images')
    )


def _is_ajax(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _is_own_listing(request, product):
    return request.user.is_authenticated and product.seller_id == request.user.pk


def _product_url(product):
    return reverse('products:detail', args=[product.slug])


def _product_or_home(product):
    # Listing yang sudah sold nggak punya halaman publik, jadi arahkan ke home aja.
    return _product_url(product) if product.is_purchasable else reverse('products:home')


def _toast(text, kind='added', **extra):
    """Pesan kecil yang muncul di bawah layar (ditampilkan oleh showToast di gaia.js)."""
    return {'kind': kind, 'text': text, **extra}


def _redirect_back(request, fallback):
    """Balik ke halaman asal form (?next=), tapi cuma kalau alamatnya masih di situs ini.

    Ini mencegah open redirect, misalnya ?next=https://situs-jahat.com.
    """
    target = request.POST.get('next') or request.GET.get('next')
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(target)
    return redirect(fallback)


def department_categories(parent, slug):
    """Empat tab kategori untuk satu departemen, dengan urutan yang tetap.

    Kalau kategorinya belum ada di database, tetap dibuatkan placeholder supaya
    tab-nya nggak loncat-loncat; isinya cuma tampil kosong.
    """
    existing = {category.name.lower(): category for category in parent.children.all()} if parent and parent.pk else {}
    return [
        existing.get(name.lower()) or Category(name=name, slug=f'{slug}-{name.lower()}')
        for name in CATEGORY_NAMES
    ]


# ---------------------------------------------------------------------------
# 2. Browsing
# ---------------------------------------------------------------------------

def home(request):
    picked = available_products().order_by('-created_at')[:5]

    # Tab Women dan Men selalu muncul, walaupun kategorinya belum di-seed.
    stored_parents = {parent.slug: parent for parent in Category.objects.filter(parent__isnull=True)}
    parents = [stored_parents.get(slug) or Category(name=slug.capitalize(), slug=slug) for slug in GENDER_ORDER]
    gender = request.GET.get('gender', 'women')
    active_parent = next((parent for parent in parents if parent.slug == gender), parents[0])

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
    """Halaman /shop/women/, /shop/men/, dan /picked/ (semua produk).

    Tab kategorinya (Tops, Bottoms, ...) menyaring card langsung di browser, tanpa request baru.
    """
    parents = Category.objects.filter(parent__isnull=True)
    products = available_products()

    if gender:
        if gender not in GENDER_ORDER:
            raise Http404('Unknown department')
        parent = parents.filter(slug=gender).first()
        products = products.filter(category__parent=parent) if parent else Product.objects.none()
        page_title = f"Shop {gender.capitalize()}'s"
        crumb = gender.capitalize()
        link_base = reverse('products:listing', args=[gender])
    else:
        parent = parents.first()
        page_title = crumb = 'Picked For You'
        link_base = reverse('products:picked')

    categories = department_categories(parent, gender or (parent.slug if parent else 'all'))
    category_slug = request.GET.get('category')
    if category_slug:
        active_category = next(
            (c for c in categories if c.slug == category_slug or c.name.lower() == category_slug.lower()), None,
        )
    else:
        active_category = categories[0]

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


def _apply_search_filters(products, price_from, price_to, genders, categories, conditions):
    # Kolom harga itu input bebas, jadi cuma angka bulat yang dipakai; selain itu diabaikan.
    if price_from.isascii() and price_from.isdigit():
        products = products.filter(price__gte=int(price_from))
    if price_to.isascii() and price_to.isdigit():
        products = products.filter(price__lte=int(price_to))
    if genders:
        products = products.filter(category__parent__slug__in=genders)
    if categories:
        products = products.filter(category__name__in=categories)
    if conditions:
        products = products.filter(condition__in=conditions)
    return products


def _search_facets(matches, genders, categories, conditions):
    """Pilihan checkbox di panel filter, masing-masing dengan jumlah produknya.

    Jumlahnya dihitung dari semua hasil kata kunci, bukan dari hasil yang sudah
    difilter, supaya opsi lain nggak tiba-tiba hilang waktu satu checkbox dicentang.
    """
    gender_options = [
        {
            'slug': parent.slug,
            'name': f'{parent.name}’s',
            'count': matches.filter(category__parent=parent).count(),
            'checked': parent.slug in genders,
        }
        for parent in sorted(
            Category.objects.filter(parent__isnull=True),
            key=lambda p: (GENDER_ORDER.index(p.slug) if p.slug in GENDER_ORDER else 99, p.name),
        )
    ]

    # "Tops" ada di Women dan Men, jadi cukup ditampilkan sekali.
    category_options = []
    seen = set()
    child_categories = sorted(
        Category.objects.filter(parent__isnull=False),
        key=lambda c: (CATEGORY_ORDER.get(c.name.lower(), 99), c.name),
    )
    for category in child_categories:
        if category.name in seen:
            continue
        seen.add(category.name)
        category_options.append({
            'name': category.name,
            'count': matches.filter(category__name=category.name).count(),
            'checked': category.name in categories,
        })

    condition_options = [
        {
            'value': value,
            'label': CONDITION_LABELS.get(value, label),
            'count': matches.filter(condition=value).count(),
            'checked': value in conditions,
        }
        for value, label in Product.Condition.choices
    ]
    return gender_options, category_options, condition_options


def search(request):
    q = request.GET.get('q', '').strip()
    if not q:
        request.session['bag_toast'] = _toast('Enter a search term.', kind='error')
        return redirect('products:home')

    # Semua produk yang cocok sama kata kunci, sebelum filter apa pun diterapkan.
    matches = available_products().select_related('category__parent').filter(
        Q(title__icontains=q)
        | Q(description__icontains=q)
        | Q(style_tags__icontains=q)
        | Q(category__name__icontains=q)
        | Q(category__parent__name__icontains=q)
    )

    price_from = request.GET.get('price_from', '').strip()
    price_to = request.GET.get('price_to', '').strip()
    genders = request.GET.getlist('gender')
    categories = request.GET.getlist('category')
    conditions = request.GET.getlist('condition')

    products = _apply_search_filters(matches, price_from, price_to, genders, categories, conditions).order_by('-created_at')
    result_count = products.count()
    gender_options, category_options, condition_options = _search_facets(matches, genders, categories, conditions)

    # Form filter pakai HTMX (lihat search.html): dia minta halaman yang sama ini, lalu
    # cuma bagian hasil dan jumlahnya yang diganti, jadi view-nya nggak perlu dibedakan.
    return render(request, 'products/search.html', {
        'q': q,
        'products': products[:60],
        'result_count': result_count,
        # Panel filter tetap ditampilkan selama kata kuncinya ada hasil, supaya kalau
        # filternya bikin hasil jadi kosong, user masih bisa balik ngubah filter.
        'has_matches': result_count > 0 or matches.exists(),
        'price_from': price_from,
        'price_to': price_to,
        'genders': gender_options,
        'category_facets': category_options,
        'conditions': condition_options,
    })


def detail(request, slug):
    product = get_object_or_404(
        Product.objects
        .select_related('category', 'category__parent', 'seller', 'seller__profile')
        .prefetch_related('images'),
        slug=slug,
    )
    # Listing sold hilang dari toko, tapi pemiliknya masih bisa buka, edit, atau hapus.
    if not product.is_purchasable and not _is_own_listing(request, product):
        raise Http404('Listing is no longer available')

    # Foto cover ditaruh paling depan, sisanya sesuai urutan yang disimpan.
    images = list(product.images.all())
    primary = product.primary_image
    if primary in images:
        images.remove(primary)
        images.insert(0, primary)

    # "Also see": produk lain dari kategori yang sama; kalau nggak ada, tampilkan produk apa aja.
    related = available_products().exclude(pk=product.pk)
    if product.category_id:
        same_category = related.filter(category=product.category)
        if same_category.exists():
            related = same_category

    saved_items = WishlistItem.objects.filter(product_key=product.slug, removed=False)
    return render(request, 'products/detail.html', {
        'product': product,
        'images': images,
        'related': related.order_by('-created_at')[:5],
        'saved_count': saved_items.count(),
        'wishlist_saved': request.user.is_authenticated and saved_items.filter(user=request.user).exists(),
    })


# ---------------------------------------------------------------------------
# 3. Jualan: bikin, edit, dan hapus listing
# ---------------------------------------------------------------------------

def _listing_form_page(request, product=None):
    """Dipakai bareng oleh "List an item" (product = None) dan "Edit listing"."""
    editing = product is not None
    is_post = request.method == 'POST'
    existing_images = list(product.images.all()) if editing else []
    form = ProductListingForm(request.POST if is_post else None, request.FILES if is_post else None, instance=product)

    if is_post and form.is_valid():
        # Listing dan foto barunya disimpan dalam satu transaksi: berhasil semua, atau batal semua.
        with transaction.atomic():
            product = form.save(commit=False)
            product.seller = request.user
            product.save()
            # Foto baru ditaruh setelah foto yang sudah ada; untuk listing baru, foto pertama jadi cover.
            next_order = max((image.order for image in existing_images), default=-1) + 1
            for index, photo in enumerate(form.cleaned_data['photos']):
                ProductImage.objects.create(
                    product=product, image=photo,
                    is_primary=not existing_images and index == 0, order=next_order + index,
                )

        message = 'Listing updated.' if editing else 'Listing created.'
        if editing or _is_ajax(request):
            request.session['bag_toast'] = _toast(message)
        if _is_ajax(request):
            # Form jual dikirim pakai fetch(); JS-nya yang nanti pindah ke redirect_url.
            return JsonResponse({
                'ok': True,
                'product_id': product.pk,
                'redirect_url': _product_url(product),
                'message': message,
            }, status=200 if editing else 201)
        return redirect(_product_url(product))

    if is_post and _is_ajax(request):
        # Error validasi dikirim balik sebagai JSON supaya form bisa menampilkannya tanpa reload.
        return JsonResponse({
            'ok': False,
            'errors': {field: list(messages) for field, messages in form.errors.items()},
        }, status=400)

    selected_category = form.cleaned_data.get('category') if form.is_bound else (product.category if editing else None)
    cover = product.primary_image if editing else None
    return render(request, 'products/sell.html', {
        'parents': list(Category.objects.filter(parent__isnull=True).prefetch_related('children').order_by('name')),
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
@rate_limit('listing-create', limit=10, window=60 * 60)
def sell(request):
    return _listing_form_page(request)


@login_required
@rate_limit('listing-edit', limit=30, window=10 * 60)
@owner_required(lambda: Product.objects.select_related('category__parent').prefetch_related('images'))
def edit(request, product):
    # owner_required sudah ngambil listing-nya dan memastikan ini milik user yang login.
    return _listing_form_page(request, product)


@login_required
@require_POST
@rate_limit('listing-delete', limit=20, window=10 * 60)
@owner_required()
def delete_listing(request, product):
    product_id = product.pk
    product.delete()
    # Bersihkan juga bag dan data undo di session seller, kalau listing ini masih tercatat di sana.
    cart.remove(request.session, product_id)
    if request.session.get('bag_undo', {}).get('product_id') == product_id:
        request.session.pop('bag_undo')

    toast = _toast('Listing deleted.')
    if _is_ajax(request):
        # Hapus dari card produk: card-nya dihapus sendiri oleh JS di halaman.
        return JsonResponse({'ok': True, 'toast': toast, 'product_id': product_id})
    request.session['bag_toast'] = toast
    return _redirect_back(request, reverse('products:home'))


# ---------------------------------------------------------------------------
# 4. Shopping bag
# ---------------------------------------------------------------------------

def _bag_json(request, *, toast=None, open_drawer=False, status=200):
    """Jawaban semua aksi bag untuk JS: jumlah item terbaru, daftar produk yang ada
    di bag (supaya tiap tombol "Add to bag" bisa ikut berubah), dan isi drawer yang baru."""
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
        # Notifikasi "Item removed / Undo" sudah ada di dalam HTML drawer, jadi bukan toast.
        'toast': toast if toast and toast.get('kind') in ('added', 'error') else None,
        'open': open_drawer,
    }, status=status)


def _bag_error(request, text, fallback, *, open_drawer=False, status=409):
    toast = _toast(text, kind='error')
    if _is_ajax(request):
        return _bag_json(request, toast=toast, open_drawer=open_drawer, status=status)
    request.session['bag_toast'] = toast
    request.session['bag_open'] = open_drawer
    return redirect(fallback)


def _bag_done(request, toast, fallback, *, open_drawer=False):
    """Aksi bag yang berhasil: JSON untuk AJAX, kalau bukan AJAX redirect plus toast."""
    if _is_ajax(request):
        return _bag_json(request, toast=toast, open_drawer=open_drawer)
    request.session['bag_toast'] = toast
    if open_drawer:
        request.session['bag_open'] = True
    return _redirect_back(request, fallback)


@require_POST
@rate_limit('bag', limit=60, window=60)
def bag_add(request, slug):
    product = get_object_or_404(Product, slug=slug)
    if not product.is_purchasable:
        return _bag_error(request, 'This item is no longer available.', reverse('products:home'))
    if _is_own_listing(request, product):
        return _bag_error(request, 'You cannot buy your own listing.', _product_url(product), status=403)

    already_in_bag = cart.quantity_for(request.session, product.pk) > 0
    cart.add(request.session, product.pk)
    text = 'This item is already in your bag.' if already_in_bag else f'Added “{product.title}” to bag'
    return _bag_done(request, _toast(text, icon=True), _product_url(product))


@require_POST
@rate_limit('bag', limit=60, window=60)
def bag_remove(request, slug):
    """Dipanggil waktu tombol "Added to bag" dipencet lagi, buat ngeluarin item dari bag."""
    product = get_object_or_404(Product, slug=slug)
    in_bag = cart.quantity_for(request.session, product.pk) > 0
    cart.remove(request.session, product.pk)
    text = f'Removed “{product.title}” from bag' if in_bag else 'This item is not in your bag.'
    return _bag_done(request, _toast(text, icon=True), _product_or_home(product))


@require_POST
@rate_limit('bag', limit=60, window=60)
def bag_set(request, slug):
    """Dipakai di drawer bag: quantity 0 artinya item dihapus, lalu muncul tombol Undo."""
    product = get_object_or_404(Product, slug=slug)
    try:
        quantity = int(request.POST.get('quantity', ''))
    except (TypeError, ValueError):
        return _bag_error(request, 'Enter a valid whole-number quantity.', _product_or_home(product), open_drawer=True, status=400)

    if quantity > 0 and not product.is_purchasable:
        return _bag_error(request, 'This item is no longer available.', reverse('products:home'), open_drawer=True)
    if quantity > 0 and _is_own_listing(request, product):
        return _bag_error(request, 'You cannot buy your own listing.', _product_url(product), open_drawer=True, status=403)
    if quantity > cart.MAX_QUANTITY:
        return _bag_error(request, 'Each listing is available only once.', _product_url(product), open_drawer=True, status=400)

    toast = None
    if quantity <= 0:
        previous = cart.quantity_for(request.session, product.pk)
        cart.remove(request.session, product.pk)
        if previous:
            # Simpan item yang barusan dihapus supaya tombol Undo bisa mengembalikannya.
            request.session['bag_undo'] = {'product_id': product.pk, 'quantity': previous}
            toast = _toast('Item removed', kind='removed', undo=True)
    else:
        cart.set_quantity(request.session, product.pk, quantity)
    return _bag_done(request, toast, _product_or_home(product), open_drawer=True)


@require_POST
@rate_limit('bag', limit=60, window=60)
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
        toast = _toast('Item added back to bag', icon=True)
    return _bag_done(request, toast, reverse('products:home'), open_drawer=True)


# ---------------------------------------------------------------------------
# 5. Wishlist
# ---------------------------------------------------------------------------

def _wish_login_required(request, product):
    # Tamu diarahkan ke login dulu, lalu balik lagi ke halaman produk setelahnya.
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
@rate_limit('wishlist', limit=40, window=60)
def wish_add(request, slug):
    product = get_object_or_404(Product, slug=slug, status=Product.Status.AVAILABLE)
    if not request.user.is_authenticated:
        return _wish_login_required(request, product)
    if _is_own_listing(request, product):
        toast = _toast('You cannot save your own listing.', kind='error')
        if _is_ajax(request):
            return JsonResponse({'ok': False, 'toast': toast}, status=403)
        request.session['bag_toast'] = toast
        return redirect(_product_url(product))

    # Wishlist menyimpan salinan judul, harga, dan foto, jadi tetap rapi walaupun listing-nya
    # berubah nanti. Kalau item yang pernah dihapus disimpan lagi, datanya cukup dipulihkan.
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
    toast = _toast(f'Saved “{product.title}” to wishlist', icon='heart')
    return _wish_response(request, product, saved=True, toast=toast)


@require_POST
@rate_limit('wishlist', limit=40, window=60)
def wish_remove(request, slug):
    product = get_object_or_404(Product, slug=slug, status=Product.Status.AVAILABLE)
    if not request.user.is_authenticated:
        return _wish_login_required(request, product)

    # Ditandai removed, bukan dihapus dari database, karena tombol Undo di halaman akun butuh data ini.
    WishlistItem.objects.filter(user=request.user, product_key=product.slug, removed=False).update(removed=True)
    toast = _toast(f'Removed “{product.title}” from wishlist', icon='heart')
    return _wish_response(request, product, saved=False, toast=toast)
