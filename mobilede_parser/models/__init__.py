from django.db.models.signals import pre_delete
from django.db.transaction import atomic
from django.dispatch import receiver

from .Ad import Ad
from .Search import Search

__all__ = ('helpers', 'Search', 'Ad')


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
        ads_to_delete = instance.ad_set.filter(pk__in=map(lambda ad: ad.site_id, ads_to_delete))
        ads_to_delete.delete()

# https://suchen.mobile.de/fahrzeuge/search.html?damageUnrepaired=NO_DAMAGE_UNREPAIRED&features=ELECTRIC_HEATED_SEATS&features=MULTIFUNCTIONAL_WHEEL&fuels=DIESEL&grossPrice=true&isSearchRequest=true&makeModelVariant1.makeId=25200&makeModelVariant1.modelId=14&maxCubicCapacity=1600&maxPrice=10500&minFirstRegistrationDate=2016-01-01&scopeId=C&sortOption.sortBy=creationTime&sortOption.sortOrder=DESCENDING&sset=1627887194&ssid=10261689&transmissions=MANUAL_GEAR&vatable=true
