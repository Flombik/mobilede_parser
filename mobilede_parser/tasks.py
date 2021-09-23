from celery import shared_task
from .models import Search, Ad


@shared_task
def parse_search(search_id, *args, **kwargs):
    search = Search.objects.get(pk=search_id)
    search.parse_ads()


@shared_task
def parse_all_searches(*args, **kwargs):
    for search in Search.objects.all():
        parse_search.delay(search.pk)


@shared_task
def renew_ad(ad_id, *args, **kwargs):
    ad = Ad.objects.get(pk=ad_id)
    ad.renew_data()


@shared_task
def renew_all_ads(*args, **kwargs):
    for ad in Ad.objects.all():
        renew_ad.delay(ad.pk)
