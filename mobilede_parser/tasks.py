from celery import shared_task
from .models import Search


@shared_task
def parse_search(search_id, *args, **kwargs):
    search = Search.objects.get(pk=search_id)
    search.parse_ads()


@shared_task
def parse_all_searches(*args, **kwargs):
    for search in Search.objects.all():
        parse_search.delay(search.pk)
