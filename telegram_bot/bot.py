from django.conf import settings
from telegram.ext import Updater

from .persistence import DjangoPersistence

updater = Updater(settings.TELEGRAM_BOT_TOKEN, persistence=DjangoPersistence())
dispatcher = updater.dispatcher
bot = updater.bot
