from django.contrib import admin
from django.contrib.admin import ModelAdmin

from .models import Search, Ad


class SearchAdmin(ModelAdmin):
    list_display = ('name', 'url')
    readonly_fields = ('created_at', 'updated_at')
    search_fields = ('name',)
    filter_horizontal = ('subscribers',)

    fieldsets = (
        (None, {'fields': ('name', 'url')}),
        ('Other', {'fields': ('subscribers', 'created_at', 'updated_at')}),
    )


admin.site.register(Search, SearchAdmin)


class AdAdmin(ModelAdmin):
    list_display = ('site_id', 'name', 'price', 'price_net', 'vat', 'date')
    readonly_fields = ('price_net', 'created_at', 'updated_at')
    search_fields = ('site_id', 'name',)
    filter_horizontal = ('searches',)
    date_hierarchy = 'date'

    fieldsets = (
        (None, {'fields': ('site_id', 'name')}),
        ('Financial Info', {'fields': ('price', 'price_net', 'vat')}),
        ('General Info', {'fields': ('date', 'description', 'url', 'image_url')}),
        ('Other', {'fields': ('searches', 'created_at', 'updated_at')}),
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


admin.site.register(Ad, AdAdmin)
