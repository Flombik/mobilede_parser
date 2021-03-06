from functools import cache

import requests
from django.conf import settings
from django.contrib.auth.views import LoginView


# TODO: refactoring. do something with:
#       <telegram_user.views.TelegramUserLoginView.get_telegram_bot_data>
#       <telegram_user.views.TelegramUserLoginView.get_telegram_bot_username>
#       <telegram_user.views.TelegramUserLoginView.TelegramUserLoginView.get_context_data>

@cache
def get_telegram_bot_data():
    response = requests.get(f'https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getMe')
    response.raise_for_status()
    response = response.json()
    return response['result']


@cache
def get_telegram_bot_username():
    return get_telegram_bot_data()['username']


class TelegramUserLoginView(LoginView):
    template_name = 'telegram_login.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'tg_bot_username': get_telegram_bot_username(),
            'tg_redirect_url': 'http://localhost.com/user/telegram_login/'
        })
        return context
