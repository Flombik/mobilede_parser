from django.conf import settings
from telegram import Bot as TGBot
from telegram.ext import Updater, Dispatcher

from .helpers import Singleton
from .persistence import DjangoPersistence


class Bot(metaclass=Singleton):
    def __init__(self):
        self.updater = Updater(settings.TELEGRAM_BOT_TOKEN, persistence=DjangoPersistence())

        self.start_polling = self.updater.start_polling
        self.start_webhook = self.updater.start_webhook
        self.idle = self.updater.idle

        self.add_handler = self.dispatcher.add_handler
        self.remove_handler = self.dispatcher.remove_handler

    def __getattr__(self, attr: str):
        if not attr.startswith('_'):
            return getattr(self.bot, attr)
        raise AttributeError(f"'{self.__class__.__name__}' don't have attribute '{attr}'")

    @property
    def dispatcher(self) -> 'Dispatcher':
        return self.updater.dispatcher

    @property
    def bot(self) -> 'TGBot':
        return self.updater.bot

    @property
    def bot_info(self) -> dict:
        return self.bot.bot.to_dict()
