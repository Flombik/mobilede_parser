import re
import unicodedata
from contextlib import suppress
from typing import Any, Dict, List, Union

import requests
from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from furl import furl

from .helpers.bases import QueryParametersModelBase
from .helpers.mixins import SessionMixin

DB_CHUNK_SIZE = 5000


class Search(QueryParametersModelBase, SessionMixin):
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
            existed_ads_ids = self.ad_set.model.objects.filter(site_id__in=ads_ids).values_list('site_id', flat=True)
            ad_to_search_links = []

            for ad_id in existed_ads_ids:
                ad_to_search_links.append(self.ad_set.model.searches.through(ad_id=ad_id, search_id=self.id))

            new_ads = [self.ad_set.model(**ad) for ad in ads_chunk if ad.get('site_id') not in existed_ads_ids]
            for ad in new_ads:
                ad_to_search_links.append(self.ad_set.model.searches.through(ad_id=ad.site_id, search_id=self.id))

            self.ad_set.model.objects.bulk_create(new_ads, DB_CHUNK_SIZE)
            self.ad_set.model.searches.through.objects.bulk_create(ad_to_search_links, DB_CHUNK_SIZE, ignore_conflicts=True)

    def parse_ads(self):
        num_of_pages = self._get_num_of_pages()
        for page_num in range(1, num_of_pages + 1):
            page = self._get_page_by_num(page_num)
            parsed_ads = self._parse_page(page)
            self._save_ads(parsed_ads)

    def get_ads(self):
        return list(self.ad_set.all())
