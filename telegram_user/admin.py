from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models import IntegerField
from django.forms import NumberInput
from django.utils.translation import gettext_lazy as _

from .forms import TelegramUserCreationForm, TelegramUserChangeForm
from .models import TelegramUser


class TelegramUserAdmin(UserAdmin):
    add_form = TelegramUserCreationForm
    form = TelegramUserChangeForm
    fieldsets = (
        (None, {'fields': ('username', 'password', 'telegram_id')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', '_photo_url')}),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    list_display = ('username', 'first_name', 'last_name', 'is_staff')
    search_fields = ('username', 'first_name', 'last_name')
    readonly_fields = ('last_login', 'date_joined')

    formfield_overrides = {
        IntegerField: {'widget': NumberInput(attrs={'max': '9999999999'})}
    }


admin.site.register(TelegramUser, TelegramUserAdmin)
