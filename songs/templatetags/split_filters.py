from django import template

register = template.Library()

@register.filter
def split(value, delimiter=None):
    """
    Splits a string into a list.
    If no delimiter is provided, splits by newline.
    """
    if not value:
        return []
    if delimiter:
        return value.split(delimiter)
    return value.splitlines()
