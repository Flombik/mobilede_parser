from django.contrib.auth.forms import UserCreationForm, UserChangeForm

from .models import TelegramUser


class TelegramUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = TelegramUser


class TelegramUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = TelegramUser
