from django.contrib.auth.views import LoginView

from telegram_bot import bot


# TODO: refactoring. do something with:
#       <telegram_user.views.TelegramUserLoginView.get_telegram_bot_username>
#       <telegram_user.views.TelegramUserLoginView.TelegramUserLoginView.get_context_data>

def get_telegram_bot_username():
    return bot.bot['username']


class TelegramUserLoginView(LoginView):
    template_name = 'telegram_login.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'tg_bot_username': get_telegram_bot_username(),
            'tg_redirect_url': 'http://localhost.com/user/telegram_login/'
        })
        return context
