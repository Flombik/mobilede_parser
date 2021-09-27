import requests
from ..functions import get_headers_for_request


class SessionMixin(object):
    def __init__(self):
        self.__session = requests.Session()

    @property
    def _session(self) -> requests.Session:
        self.__session.headers.update(get_headers_for_request())
        return self.__session
