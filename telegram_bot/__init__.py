from django.conf import settings
from telegram.ext import Updater

updater = Updater(settings.TELEGRAM_BOT_TOKEN)
dispatcher = updater.dispatcher
bot = updater.bot

__all__ = ('updater', 'dispatcher', 'bot')
