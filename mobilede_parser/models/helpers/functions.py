import random
from typing import Dict, Union

from django.conf import settings


def get_headers_for_request() -> Dict[str, Union[str, int]]:
    headers = {
        'User-Agent': random.choice(settings.PARSER_USER_AGENTS_LIST),
    }
    return headers
