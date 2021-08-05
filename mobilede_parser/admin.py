from django.contrib import admin
from django.contrib.admin import ModelAdmin

from .models import Search, Ad


class SearchAdmin(ModelAdmin):
    list_display = ('name', 'url')
    search_fields = ('name',)
    filter_horizontal = ('subscribers',)


admin.site.register(Search, SearchAdmin)


class AdAdmin(ModelAdmin):
    list_display = ('site_id', 'name', 'price', 'price_net', 'vat', 'date')
    readonly_fields = ('price_net',)
    search_fields = ('site_id', 'name',)
    filter_horizontal = ('searches',)
    date_hierarchy = 'date'

    fieldsets = (
        (None, {'fields': ('site_id', 'name')}),
        ('Financial Info', {'fields': ('price', 'price_net', 'vat')}),
        ('General Info', {'fields': ('date', 'description', 'url', 'image_url')}),
        ('Other', {'fields': ('searches',)}),
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


admin.site.register(Ad, AdAdmin)
