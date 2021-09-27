import re
import time
from math import ceil

import requests
from bs4 import BeautifulSoup
from django.contrib import admin
from django.db import models
from django.db.models import F, Value
from django.db.models.functions import Ceil

from .Search import Search
from .helpers.bases import QueryParametersModelBase
from .helpers.mixins import SessionMixin

try:
    import selenium
except ImportError:
    SELENIUM_IS_AVAILABLE = False
else:
    from selenium.webdriver import Chrome, ChromeOptions

    SELENIUM_IS_AVAILABLE = True

DB_CHUNK_SIZE = 5000


class Ad(QueryParametersModelBase, SessionMixin):
    root_url = 'https://suchen.mobile.de/fahrzeuge/details.html'

    single_value_fields = ('id', 'fnai', 'searchId', 'action') + Search.single_value_fields
    multiple_value_fields = Search.multiple_value_fields
    overriding_params = {'lang': 'en'}

    site_id = models.IntegerField(primary_key=True, db_index=True)

    name = models.CharField(max_length=1024, blank=True)
    price = models.PositiveIntegerField(null=True, blank=True)
    vat = models.PositiveSmallIntegerField(null=True, blank=True)
    date = models.DateTimeField(null=True, blank=True)
    description = models.TextField(max_length=4096, blank=True)
    image_url = models.URLField(max_length=2048, blank=True)

    searches = models.ManyToManyField('mobilede_parser.Search')

    created_at = models.DateTimeField('creation date', auto_now_add=True)
    updated_at = models.DateTimeField('last updated', auto_now=True)

    def __str__(self):
        return self.name

    @property
    @admin.display(ordering=Ceil(F('price') - F('price') * F('vat') / Value(100)))
    def price_net(self) -> int:
        return ceil(self.price * (1 - self.vat / 100))

    def _get_page(self, session: requests.Session = None) -> bytes:
        if SELENIUM_IS_AVAILABLE:
            webdriver_options = ChromeOptions()
            webdriver_options.add_argument('--headless')
            webdriver_options.add_argument('--no-sandbox')
            # webdriver_options.add_argument("--window-size=854,480")
            webdriver_options.add_argument(
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Safari/537.36"
            )
            with Chrome(options=webdriver_options) as webdriver:
                # webdriver.set_window_size(854,480)
                webdriver.get(self.url)
                time.sleep(4)
                content = webdriver.page_source
        else:
            if session is None:
                session = self._session
            response = session.get(self.url)
            content = response.content

        return content

    def _parse_page(self, page: bytes = None, session: requests.Session = None):
        if page is None:
            page = self._get_page(session=session)

        soup = BeautifulSoup(page, 'lxml')
        viewport = soup.find('div', 'viewport')
        try:
            main = viewport.div.contents[1].find_all('div', 'g-row', recursive=False)[-1]
        except AttributeError:
            return {}

        name = main.find('h1', id='ad-title').text
        name = re.sub(r'\s+', ' ', name).strip()

        price = main.find('span', attrs={'data-testid': 'prime-price'}).text
        price = int(re.sub(r'\D+', '', price))

        try:
            vat = main.find('span', attrs={'data-testid': 'vat'}).text
            vat = round(
                float(re.sub(r'[^\d,.]+|^[.,]|[.,]$', '', vat).replace(',', '.'))
            )
        except (AttributeError, ValueError):
            vat = None

        img_el = main.find('img')
        try:
            image_url = img_el.get('src') or img_el.get('data-src')
            if image_url.startswith('//'):
                image_url = 'https:' + image_url
            image_url = re.sub(r'\$_\d+', '$_10', image_url)
        except AttributeError:
            image_url = None

        data = {
            'name': name,
            'price': price,
            'vat': vat,
            # 'description': description, ??
            'image_url': image_url,
        }

        return data

    def renew_data(self):
        page = self._get_page()
        data = self._parse_page(page)
        if data:
            for key, value in data.items():
                setattr(self, key, value)
            self.save()
