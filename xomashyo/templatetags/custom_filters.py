from django import template

register = template.Library()

@register.filter
def mul(value, arg):
    """Ko'paytirish filteri"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0
