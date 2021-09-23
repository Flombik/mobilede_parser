import random
import re
import time
import unicodedata
from collections import defaultdict
from contextlib import suppress
from math import ceil
from typing import Any, Dict, List, Union

import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import F, Value
from django.db.models.functions import Ceil
from django.db.models.signals import pre_delete
from django.db.transaction import atomic
from django.dispatch import receiver
from django.utils import timezone
from furl import furl
from telegram_user.tasks import notify_user as async_notify_user

try:
    import selenium
except ImportError:
    SELENIUM_IS_AVAILABLE = False
else:
    from selenium.webdriver import Chrome, ChromeOptions

    SELENIUM_IS_AVAILABLE = True

DB_CHUNK_SIZE = 5000

MESSAGE_TEMPLATE = r"We found new car from your favorites searches\! Here is [link]({ad_link}) for the ad\."


def get_headers_for_request() -> Dict[str, Union[str, int]]:
    headers = {
        'User-Agent': random.choice(settings.PARSER_USER_AGENTS_LIST),
    }
    return headers


class ParametersValidationError(Exception):
    def __init__(self, message, *args):
        super().__init__(message, *args)


class QueryParametersMixin(models.Model):
    class Meta:
        abstract = True

    root_url = ''
    single_value_fields = ()
    multiple_value_fields = ()

    overriding_params = {}
    excluding_params = ()

    @property
    def fields(self):
        return self.single_value_fields + self.multiple_value_fields

    parameters = models.JSONField(default=dict)

    @staticmethod
    def _parse_url(url) -> tuple[furl, dict]:
        url = furl(url)
        params = defaultdict(list)
        for key, value in url.args.iterallitems():
            if value is not None:
                params[key].append(value)
            else:
                params.setdefault('key')
        params = {
            key: None if not value else value[0] if len(value) == 1 else value
            for key, value in params.items()
        }
        return url, params

    def _validate_params(self, params: dict):
        for key, value in params.items():
            if key not in self.fields:
                raise ParametersValidationError(f'Parameter "{key}" is not allowed.')
            if key in self.single_value_fields and type(value) is list:
                raise ParametersValidationError(f'Value of parameter "{key}" must be single.')

    @property
    def url(self) -> str:
        params = self.parameters | self.overriding_params
        for param in self.excluding_params:
            params.pop(param, None)
        url = furl(self.root_url, query_params=params)
        return url.url

    @url.setter
    def url(self, url):
        url, params = self._parse_url(url)
        if furl(self.root_url).origin != url.origin:
            raise ParametersValidationError('URL origin must match root URL.')
        self._validate_params(params)
        self.parameters = params


class SessionMixin(object):
    def __init__(self):
        self.__session = requests.Session()

    @property
    def _session(self) -> requests.Session:
        self.__session.headers.update(get_headers_for_request())
        return self.__session


class Search(QueryParametersMixin, SessionMixin):
    root_url = 'https://suchen.mobile.de/fahrzeuge/search.html'
    single_value_fields = (
        'adLimitation',
        'airbag',
        'ambit-search-radius',
        'av',
        'climatisation',
        'cn',
        'damageUnrepaired',
        'daysAfterCreation',
        'doorCount',
        'emissionClass',
        'emissionsSticker',
        'export',
        'grossPrice',
        'isSearchRequest',
        'lang',
        'makeModelVariant1.makeId',
        'makeModelVariant1.modelDescription',
        'makeModelVariant1.modelId',
        'makeModelVariant2.makeId',
        'makeModelVariant2.modelDescription',
        'makeModelVariant2.modelId',
        'makeModelVariantExclusions[0].makeId',
        'makeModelVariantExclusions[0].modelId',
        'maxBatteryCapacity',
        'maxConsumptionCombined',
        'maxCubicCapacity',
        'maxFirstRegistrationDate',
        'maxMileage',
        'maxPrice',
        'maxSeats',
        'minBatteryCapacity',
        'minCubicCapacity',
        'minFirstRegistrationDate',
        'minHu',
        'minMileage',
        'minPrice',
        'minSeats',
        'ms',
        'null',
        'numberOfPreviousOwners',
        'od',
        'pageNumber',
        'readyToDrive',
        'sb',
        'scopeId',
        'sfmr',
        'sld',
        'sortOption.sortBy',
        'sortOption.sortOrder',
        'spc',
        'sr',
        'sset',
        'ssid',
        'tct',
        'usedCarSeals',
        'vatable',
        'withImage',
    )
    multiple_value_fields = (
        'bat',
        'bds',
        'blt',
        'categories',
        'colors',
        'drl',
        'features',
        'fuels',
        'hlt',
        'interiorColors',
        'interiorTypes',
        'maxPowerAsArray',
        'minPowerAsArray',
        'parkAssistents',
        'rad',
        'redPencil',
        'transmissions',
        'usage',
        'usageType',
        'videoEnabled',
    )
    overriding_params = {
        'isSearchRequest': 'true',
        'lang': 'en',
    }
    excluding_params = ('pageNumber',)

    name = models.CharField(max_length=1024)
    subscribers = models.ManyToManyField(get_user_model(), blank=True)

    created_at = models.DateTimeField('creation date', auto_now_add=True)
    updated_at = models.DateTimeField('last updated', auto_now=True)

    def __str__(self):
        return self.name

    def _get_num_of_pages(self, session: requests.Session = None) -> int:
        if session is None:
            session = self._session
        response = session.get(self.url)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'lxml')
        pagination = soup.find('ul', 'pagination')
        max_page = 0
        try:
            for li in pagination.find_all('li'):
                with suppress(ValueError):
                    if (cur_page := int(li.text)) > max_page:
                        max_page = cur_page
        except AttributeError:
            return 1
        return max_page

    def _get_page_by_num(self, page_num: int, session: requests.Session = None) -> bytes:
        if session is None:
            session = self._session
        response = session.get(self.url, params={'pageNumber': page_num})
        response.raise_for_status()

        return response.content

    def _parse_page(self, page: Union[int, bytes]) -> List[Dict[str, Any]]:
        if type(page) is int:
            page = self._get_page_by_num(page)
        soup = BeautifulSoup(page, 'lxml')
        content = soup.find('div', 'cBox--resultList')
        page_ads = content.find_all('div', re.compile(r'cBox-body--(?:resultitem|eyeCatcher)'))
        ads = []
        for ad in page_ads:
            url = ad.find('a').get('href')
            site_id = int(furl(url).args.getlist('id')[0])
            headline_block = ad.find('div', 'headline-block')

            headline_block = headline_block.find_all('span')
            headline_block = list(
                filter(
                    lambda span: {'new-headline-label'} - set(span.get('class')),
                    headline_block,
                )
            )

            try:
                name, date = headline_block
                name = name.text.strip()
                date = date.text.strip()

                date = timezone.datetime.strptime(date, 'Ad online since %b %d, %Y, %I:%M %p')
                current_timezone = timezone.get_current_timezone()
                date = current_timezone.localize(date)
            except ValueError:
                date = None
                name = headline_block[0].text.strip()

            price_block = ad.find('div', 'price-block')
            try:
                price, vat = price_block.find_all('span')[:2]
                price = int(re.sub(r'\D', '', price.text).strip())
                vat = round(float(re.sub(r'[^\d,.]', '', vat.text).replace(',', '.')))
            except ValueError:
                vat = None
                price = int(re.sub(r'\D', '', price_block.find('span').text).strip())

            description = re.sub(
                r'(?:\s+)?(?:</?.*?>)+(?:\s+)?',
                ' ',
                str(ad.find('div', re.compile(r'^vehicle-data')))
            ).strip()
            description = unicodedata.normalize('NFKD', description)

            image_block = ad.find('div', 'image-block')
            try:
                img_el = image_block.find('img')
                image_url = img_el.get('src') or img_el.get('data-src')
                if image_url.startswith('//'):
                    image_url = 'https:' + image_url
                image_url = re.sub(r'\$_\d+', '$_10', image_url)
            except AttributeError:
                image_url = ''

            data = {
                'url': url,
                'site_id': site_id,
                'name': name,
                'date': date,
                'price': price,
                'vat': vat,
                'description': description,
                'image_url': image_url,
            }
            ads.append(data)
        return ads

    def _save_ads(self, ads: List[Dict[str, Any]]) -> None:
        def chunkify(itr, n):
            for i in range(0, len(itr), n):
                yield itr[i:i + n]

        ads_chunks = chunkify(ads, DB_CHUNK_SIZE)
        for ads_chunk in ads_chunks:
            ads_ids = {ad.get('site_id') for ad in ads_chunk}
            existed_ads_ids = Ad.objects.filter(site_id__in=ads_ids).values_list('site_id', flat=True)
            ad_to_search_links = []

            for ad_id in existed_ads_ids:
                ad_to_search_links.append(Ad.searches.through(ad_id=ad_id, search_id=self.id))

            new_ads = [Ad(**ad) for ad in ads_chunk if ad.get('site_id') not in existed_ads_ids]
            for ad in new_ads:
                ad_to_search_links.append(Ad.searches.through(ad_id=ad.site_id, search_id=self.id))
                for user_id in self.subscribers.values_list('id', flat=True):
                    async_notify_user.delay(
                        user_id,
                        MESSAGE_TEMPLATE.format(ad_link=ad.url),
                        image_url=ad.image_url,
                    )

            Ad.objects.bulk_create(new_ads, DB_CHUNK_SIZE)
            Ad.searches.through.objects.bulk_create(ad_to_search_links, DB_CHUNK_SIZE, ignore_conflicts=True)

    def parse_ads(self):
        num_of_pages = self._get_num_of_pages()
        for page_num in range(1, num_of_pages + 1):
            page = self._get_page_by_num(page_num)
            parsed_ads = self._parse_page(page)
            self._save_ads(parsed_ads)

    def get_ads(self):
        return list(self.ad_set.all())


class Ad(QueryParametersMixin, SessionMixin):
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
            webdriver_options.add_argument('--disable-dev-shm-usage')
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


@receiver(pre_delete, sender=Search)
def searches_changed(sender, instance, *args, **kwargs):
    sql_query = (
        "SELECT ad_id as site_id "
        "FROM mobilede_parser_ad_searches "
        f"WHERE ad_id IN (SELECT ad_id FROM mobilede_parser_ad_searches WHERE search_id = '{instance.pk}') "
        "GROUP BY ad_id "
        "HAVING COUNT(*) = 1;"
    )
    with atomic():
        ads_to_delete = instance.ad_set.raw(sql_query)
        ads_to_delete = instance.ad_set.filter(pk__in=ads_to_delete)
        ads_to_delete.delete()

# https://suchen.mobile.de/fahrzeuge/search.html?damageUnrepaired=NO_DAMAGE_UNREPAIRED&features=ELECTRIC_HEATED_SEATS&features=MULTIFUNCTIONAL_WHEEL&fuels=DIESEL&grossPrice=true&isSearchRequest=true&makeModelVariant1.makeId=25200&makeModelVariant1.modelId=14&maxCubicCapacity=1600&maxPrice=10500&minFirstRegistrationDate=2016-01-01&scopeId=C&sortOption.sortBy=creationTime&sortOption.sortOrder=DESCENDING&sset=1627887194&ssid=10261689&transmissions=MANUAL_GEAR&vatable=true
