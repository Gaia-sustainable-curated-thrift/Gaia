from django import template
register = template.Library()

@register.filter
def rupiah(value):
    return 'Rp' + format(int(value), ',').replace(',', '.')


@register.filter
def initials(user):
    name = user.get_full_name() or user.username
    return ''.join(part[0] for part in name.split()[:2]).upper()


@register.filter
def product_image_url(value):
    from urllib.parse import urlsplit
    from django.templatetags.static import static
    value = str(value or '')
    try:
        parsed = urlsplit(value)
    except ValueError:
        return ''
    if parsed.scheme:
        return value if parsed.scheme in ('http', 'https') and parsed.netloc else ''
    if not value or value.startswith('//') or '\\' in value:
        return ''
    return value if value.startswith('/') else static(value)
