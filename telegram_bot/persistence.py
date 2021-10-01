from collections import defaultdict
from logging import getLogger
from typing import Dict, Tuple, Any, Callable, Optional

from django.db.transaction import atomic
from telegram.ext import DictPersistence
from telegram.utils.helpers import (
    encode_conversations_to_json,
    decode_conversations_from_json,
)

from .models import Persistence

try:
    import ujson as json
except ImportError:
    import json


class DjangoPersistence(DictPersistence):
    """Using Django ORM to make user/chat/bot data persistent across reboots.

    Attributes:
        store_user_data (:obj:`bool`): Whether user_data should be saved by this
            persistence class.
        store_chat_data (:obj:`bool`): Whether chat_data should be saved by this
            persistence class.
        store_bot_data (:obj:`bool`): Whether bot_data should be saved by this
            persistence class.

    Args:
        url (:obj:`str`, Optional) the postgresql database url.
        session (:obj:`scoped_session`, Optional): sqlalchemy scoped session.
        on_flush (:obj:`bool`, optional): if set to :obj:`True` :class:`PostgresPersistence`
            will only update bot/chat/user data when :meth:flush is called.
        **kwargs (:obj:`dict`): Arbitrary keyword Arguments to be passed to
            the DictPersistence constructor.
    """

    def __init__(
            self,
            on_flush: bool = False,
            **kwargs: Any,
    ) -> None:

        self.logger = getLogger(__name__)
        super().__init__(**kwargs)

        self.on_flush = on_flush
        self.__load_database()

    def __load_database(self) -> None:
        persistence, _ = Persistence.objects.get_or_create()
        data = persistence.data

        self.logger.info("Loading database....")
        self._chat_data = defaultdict(dict, self._key_mapper(data.get("chat_data", {}), int))
        self._user_data = defaultdict(dict, self._key_mapper(data.get("user_data", {}), int))
        self._bot_data = data.get("bot_data", {})
        self._conversations = decode_conversations_from_json(data.get("conversations", "{}"))
        self.logger.info("Database loaded successfully!")

    @staticmethod
    def _key_mapper(iterable: Dict, func: Callable) -> Dict:
        return {func(k): v for k, v in iterable.items()}

    def _dump_into_dict(self) -> Any:
        """Dumps data into dict."""

        dump = {
            "chat_data": self._chat_data,
            "user_data": self._user_data,
            "bot_data": self.bot_data,
            "conversations": encode_conversations_to_json(self._conversations),
        }
        self.logger.debug("Dumping %s", dump)
        return dump

    def _dump_into_json(self) -> Any:
        """Dumps data into json format for inserting in db."""

        to_dump = self._dump_into_dict()
        return json.dumps(to_dump)

    def _update_database(self) -> None:
        self.logger.debug("Updating database...")
        try:
            with atomic():
                persistence = Persistence.objects.get()
                persistence.data = self._dump_into_dict()
                persistence.save()
        except Exception as ex:
            self.logger.error(
                "Failed to save data in the database.\nLogging exception: ",
                exc_info=ex,
            )

    def update_conversation(
            self, name: str, key: Tuple[int, ...], new_state: Optional[object]
    ) -> None:
        """Will update the conversations for the given handler.
        Args:
            name (:obj:`str`): The handler's name.
            key (:obj:`tuple`): The key the state is changed for.
            new_state (:obj:`tuple` | :obj:`any`): The new state for the given key.
        """
        super().update_conversation(name, key, new_state)
        if not self.on_flush:
            self._update_database()

    def update_user_data(self, user_id: int, data: Dict) -> None:
        """Will update the user_data (if changed).
        Args:
            user_id (:obj:`int`): The user the data might have been changed for.
            data (:obj:`dict`): The :attr:`telegram.ext.Dispatcher.user_data` ``[user_id]``.
        """
        super().update_user_data(user_id, data)
        if not self.on_flush:
            self._update_database()

    def update_chat_data(self, chat_id: int, data: Dict) -> None:
        """Will update the chat_data (if changed).
        Args:
            chat_id (:obj:`int`): The chat the data might have been changed for.
            data (:obj:`dict`): The :attr:`telegram.ext.Dispatcher.chat_data` ``[chat_id]``.
        """
        super().update_chat_data(chat_id, data)
        if not self.on_flush:
            self._update_database()

    def update_bot_data(self, data: Dict) -> None:
        """Will update the bot_data (if changed).
        Args:
            data (:obj:`dict`): The :attr:`telegram.ext.Dispatcher.bot_data`.
        """
        super().update_bot_data(data)
        if not self.on_flush:
            self._update_database()

    def flush(self) -> None:
        """Will be called by :class:`telegram.ext.Updater` upon receiving a stop signal. Gives the
        persistence a chance to finish up saving or close a database connection gracefully.
        """
        self._update_database()
        self.logger.info("Closing database...")
