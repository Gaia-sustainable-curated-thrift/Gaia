from django import template
register = template.Library()

@register.filter
def rupiah(value):
    return 'Rp' + format(int(value), ',').replace(',', '.')


@register.filter
def initials(user):
    name = user.get_full_name() or user.username
    return ''.join(part[0] for part in name.split()[:2]).upper()
