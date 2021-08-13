import datetime
import random
import re
from contextlib import suppress
from math import ceil
from typing import Dict, List, Union, Any
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Value, F, Count
from django.db.models.functions import Ceil
from django.db.models.signals import pre_delete
from django.db.transaction import atomic
from django.dispatch import receiver

DB_CHUNK_SIZE = 5000


class Search(models.Model):
    url = models.URLField(max_length=2048, null=False, db_index=True)
    name = models.CharField(max_length=1024)
    subscribers = models.ManyToManyField(get_user_model(), blank=True)

    created_at = models.DateTimeField('creation date', auto_now_add=True)
    updated_at = models.DateTimeField('last updated', auto_now=True)

    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #
    #     self.__session = requests.Session()
    #
    # @property
    # def _session(self) -> requests.Session:
    #     self.__session.headers.update(self._get_headers_for_request())
    #     return self.__session

    def __str__(self):
        return self.name

    @staticmethod
    def _get_headers_for_request() -> Dict[str, Union[str, int]]:
        headers = {
            'User-Agent': random.choice(settings.PARSER_USER_AGENTS_LIST),
        }
        return headers

    def _get_num_of_pages(self) -> int:
        headers = self._get_headers_for_request()
        response = requests.get(self.url, headers=headers)
        response.raise_for_status()
        # session = self._session
        # response = session.get(self.url)

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

    def _get_page_by_num(self, page_num: int) -> bytes:
        headers = self._get_headers_for_request()
        response = requests.get(self.url, headers=headers, params={'pageNumber': page_num, 'lang': 'en'})
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
            site_id = int(parse_qs(urlparse(url).query)['id'][0])
            headline_block = ad.find('div', 'headline-block')

            headline_block = headline_block.find_all('span')
            if len(headline_block) == 3:
                headline_block = headline_block[1:]

            try:
                name, date = headline_block
                name = name.text.strip()
                date = date.text.strip()
                date = datetime.datetime.strptime(date, 'Ad online since %b %d, %Y, %I:%M %p')
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

            image_block = ad.find('div', 'image-block')
            try:
                image_url = image_block.find('img').get('data-src')
                if image_url.startswith('//'):
                    image_url = 'https:' + image_url
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

        # TODO: think about including existed ads to "search obj" if they in results
        ads_chunks = chunkify(ads, DB_CHUNK_SIZE)
        for ads_chunk in ads_chunks:
            with atomic():
                for ad in ads_chunk:
                    site_id = ad.pop('site_id')
                    self.ad_set.update_or_create(site_id=site_id, defaults=ad)

    def parse_ads(self):
        num_of_pages = self._get_num_of_pages()
        for page_num in range(1, num_of_pages + 1):
            page = self._get_page_by_num(page_num)
            parsed_ads = self._parse_page(page)
            self._save_ads(parsed_ads)

    def get_ads(self):
        return list(self.ad_set.all())


class Ad(models.Model):
    site_id = models.IntegerField(primary_key=True, db_index=True)
    url = models.URLField(max_length=2048, null=False)

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
    @admin.display(
        ordering=Ceil(F('price') - F('price') * F('vat') / Value(100))
    )
    def price_net(self) -> int:
        return ceil(self.price * (1 - self.vat / 100))


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
