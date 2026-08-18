import json

from .india_locations import INDIA_STATES_CITIES


def india_locations(request):
    return {
        'india_states_cities': INDIA_STATES_CITIES,
        'india_cities_json': json.dumps(INDIA_STATES_CITIES, ensure_ascii=False),
    }


def nav_notifications(request):
    """Latest UNREAD notifications + unread count for the navbar bell on
    every page. Read notifications disappear from the bell entirely."""
    if not request.user.is_authenticated:
        return {'recent_notifs': [], 'unread_notifs_count': 0}
    from apps.core.models import Notification
    qs = Notification.objects.filter(recipient=request.user)
    return {
        'recent_notifs': qs.filter(is_read=False).order_by('-created_at')[:5],
        'unread_notifs_count': qs.filter(is_read=False).count(),
    }
