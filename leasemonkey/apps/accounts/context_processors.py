import json

from .india_locations import INDIA_STATES_CITIES


def india_locations(request):
    return {
        'india_states_cities': INDIA_STATES_CITIES,
        'india_cities_json': json.dumps(INDIA_STATES_CITIES, ensure_ascii=False),
    }
