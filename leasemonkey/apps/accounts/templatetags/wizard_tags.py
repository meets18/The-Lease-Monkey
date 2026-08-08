from django import template

register = template.Library()

@register.filter
def split(value, sep=','):
    return value.split(sep)

@register.filter
def get_item(mapping, key):
    """Look up a value in a dict by a variable key (e.g. {{ d|get_item:notif.id }})."""
    try:
        return mapping.get(key)
    except AttributeError:
        return None
