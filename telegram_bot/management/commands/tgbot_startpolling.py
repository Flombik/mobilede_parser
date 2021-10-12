import logging
from collections import namedtuple, OrderedDict
from contextlib import suppress
from typing import TYPE_CHECKING, Optional, Union, Any, Iterable, Callable
from django.db.models import QuerySet

from django.core.management.base import BaseCommand
from django.core.paginator import Paginator, EmptyPage
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    CommandHandler,
    CallbackContext,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    Filters,
    Handler,
)

if TYPE_CHECKING:
    from telegram.ext import Dispatcher
    from telegram.ext.handler import CCT, UT

from mobilede_parser.models import Search
from mobilede_parser.models.helpers.bases.QueryParametersModelBase import ParametersValidationError
from telegram_user.models import TelegramUser
from ...bot import Bot

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)


class DjangoUserHandler(Handler):
    def __init__(self):
        super().__init__(lambda update, context: None)

    def check_update(self, update: object) -> Optional[Union[bool, object]]:
        if isinstance(update, Update) and update.effective_user:
            return True
        return None

    def collect_additional_context(
            self,
            context: 'CCT',
            update: 'UT',
            dispatcher: 'Dispatcher',
            check_result: Any,
    ) -> None:
        default_info_list = [
            'username',
            'first_name',
            'last_name'
        ]
        tg_user = update.effective_user.to_dict()
        tg_id = tg_user.pop('id')

        db_user, created = TelegramUser.objects.get_or_create(
            telegram_id=tg_id,
            defaults={k: v for k, v in tg_user.items()
                      if k in default_info_list}
        )

        def check_attrs(attr_list: list, first, second):
            for attr_ in attr_list:
                if getattr(first, attr_) != getattr(second, attr_):
                    return False
            return True

        if not created and not check_attrs(default_info_list, namedtuple('tg_user', tg_user)(**tg_user), db_user):
            for attr, value in tg_user.items():
                if attr in default_info_list:
                    setattr(db_user, attr, value)
            db_user.save()

        context.django_user = db_user


def generate_pagination(
        current_page: int,
        page_count: int,
        callback_data_pattern: str = None,
) -> list[InlineKeyboardButton]:
    """"""

    first_page_label = '« {}'
    previous_page_label = '‹ {}'
    next_page_label = '{} ›'
    last_page_label = '{} »'
    current_page_label = '·{}·'

    if callback_data_pattern is None:
        callback_data_pattern = "{}"

    if page_count == 1:
        return list()

    keyboard_dict = OrderedDict()

    if page_count <= 5:
        for page in range(1, page_count + 1):
            keyboard_dict[page] = page
    else:
        if current_page <= 3:
            for page in range(1, 4):
                keyboard_dict[page] = page
            keyboard_dict[4] = next_page_label.format(4)
            keyboard_dict[page_count] = last_page_label.format(page_count)
        elif current_page >= page_count - 2:
            keyboard_dict[1] = first_page_label.format(1)
            keyboard_dict[page_count - 3] = previous_page_label.format(page_count - 3)
            for page in range(page_count - 2, page_count + 1):
                keyboard_dict[page] = page
        else:
            keyboard_dict[1] = first_page_label.format(1)
            keyboard_dict[current_page - 1] = previous_page_label.format(current_page - 1)
            keyboard_dict[current_page] = current_page
            keyboard_dict[current_page + 1] = next_page_label.format(current_page + 1)
            keyboard_dict[page_count] = last_page_label.format(page_count)

    keyboard_dict[current_page] = current_page_label.format(current_page)

    return [
        InlineKeyboardButton(value, callback_data=callback_data_pattern.format(key))
        for key, value in keyboard_dict.items()
    ]


def generate_paginated_view(
        objects: Iterable,
        current_page_number: int,
        object_formatting_function: Callable,
        objects_per_page: int = 5,
        objects_separator: str = "\n\n",
        before_pagination: Optional[list[InlineKeyboardButton]] = None,
        after_pagination: Optional[list[InlineKeyboardButton]] = None,
        pagination_callback_data_pattern: Optional[str] = None,
) -> tuple[str, InlineKeyboardMarkup]:
    """"""

    paginator = Paginator(objects, objects_per_page)
    current_page = paginator.get_page(current_page_number)
    page_count = paginator.num_pages

    formatted_objects: Iterable[str] = map(object_formatting_function, current_page.object_list)
    page_text = objects_separator.join(formatted_objects)

    keyboard: list[list[InlineKeyboardButton]] = list()

    pagination = generate_pagination(current_page_number, page_count, pagination_callback_data_pattern)

    if before_pagination:
        keyboard.append(before_pagination)
    keyboard.append(pagination)
    if after_pagination:
        keyboard.append(after_pagination)

    reply_markup = InlineKeyboardMarkup(keyboard)

    return page_text, reply_markup


def generate_searches_view(
        searches_list: Union[list[Search], QuerySet[Search]],
        current_page_number: int,
        objects_per_page: int = 5,
        pagination_callback_data_pattern: Optional[str] = None,
) -> tuple[str, InlineKeyboardMarkup]:
    def format_search(search: Search) -> str:
        text = f'{search.pk} - {search.name}'
        return text

    return generate_paginated_view(
        searches_list,
        current_page_number,
        format_search,
        objects_per_page,
        pagination_callback_data_pattern=pagination_callback_data_pattern,
    )


TelegramCommand = namedtuple('TelegramCommand', ['command', 'description'])


def start(update: Update, context: CallbackContext) -> None:
    """Start the conversation, display any stored data and ask user for input."""

    db_user = context.django_user

    update.message.reply_text(
        f"Hello @{db_user.username}!\n"
        "I'm \"SearchBot for mobile.de\" and I'll help you to be informed about all your searches of interest.\n"
        "To see list of my commands use /help."
    )


def stop(update: Update, context: CallbackContext) -> None:
    db_user = context.django_user

    keyboard = [
        [
            InlineKeyboardButton("Yes, I'm sure", callback_data='delete_yes'),
            InlineKeyboardButton("No, I don't", callback_data='delete_no'),
        ],
    ]

    update.message.reply_text(
        'All your data is going to be deleted. Are you sure?',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


def stop_confirmation(update: Update, context: CallbackContext) -> None:
    db_user = context.django_user

    query = update.callback_query
    query.answer()
    confirmation = query.data
    if confirmation == 'delete_yes':
        # db_user.delete()
        # context.user_data.clear()
        message_text = "Data was deleted."
    else:
        message_text = "Data wasn't deleted."

    query.edit_message_text(message_text)


def help_command(update: Update, context: CallbackContext):
    db_user = context.django_user

    commands_with_descriptions = [
        TelegramCommand("start", "start bot"),
        TelegramCommand("stop", "stop bot and remove all user data"),
        TelegramCommand("help", "just show all bot commands with their description"),
        TelegramCommand("search_list", "show all user's searches"),
        TelegramCommand("search_add", "add new search into user list"),
        TelegramCommand("search_del", "delete search from user list"),
        TelegramCommand("notification", "turn on/off notification"),
        TelegramCommand("get_updates", "force notification of current user"),
    ]

    def format_command(command: TelegramCommand):
        return f"/{command.command}", command.description

    text = "\n".join([
        " - ".join(formatted_command)
        for formatted_command
        in map(format_command, commands_with_descriptions)
    ])

    update.message.reply_text(text)


def search_list(update: Update, context: CallbackContext):
    db_user = context.django_user

    def format_search(search: Search):
        text = f'{search.pk} - {search.name}'
        return text

    if query := update.callback_query:
        current_page_num = int(query.data[3:])
    else:
        current_page_num = 1

    searches = db_user.search_set.order_by('pk').all()
    searches_count = searches.count()

    if searches_count == 0:
        update.message.reply_text("You don't add any Searches to favorites yet.")
        return
    else:
        text, reply_markup = generate_searches_view(
            searches,
            current_page_num,
            pagination_callback_data_pattern="sl_{}"
        )

        if not query:
            update.message.reply_text(text, reply_markup=reply_markup)
        else:
            query.edit_message_text(text, reply_markup=reply_markup)


########################################################################################################################

# It's the states for search adding (SA) process


SA_CHOOSING_INPUT_TYPE, SA_ENTERING_NAME, SA_ENTERING_URL, SA_SHOWING_LIST = range(4)


def sa_choose_input_type(update: Update, context: CallbackContext) -> int:
    keyboard = [
        [
            InlineKeyboardButton('Choose from existing Searches', callback_data='sa_choose'),
            InlineKeyboardButton('Create new one', callback_data='sa_create'),
        ]
    ]
    update.message.reply_text(
        'How do you want to add search to your favorites list? Please, choose one of the options.',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SA_CHOOSING_INPUT_TYPE


def sa_tmp(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.edit_message_text('Please, enter the name')
    # update.message.reply_text('Please, enter the name')
    return SA_ENTERING_NAME


def sa_name_input(update: Update, context: CallbackContext) -> int:
    name = update.message.text.strip()
    context.user_data['search_name'] = name
    update.message.reply_text(
        'Please, enter the URL now.'
    )

    return SA_ENTERING_URL


def sa_url_input(update: Update, context: CallbackContext) -> int:
    db_user = context.django_user

    text = update.message.text.strip()
    if not text:
        reply_text = "No URL provided."
        status = SA_ENTERING_URL
    else:
        text = text.split()
        if len(text) > 1:
            reply_text = "Can't add multiple searches at time. Please provide only one URL."
            status = SA_ENTERING_URL
        else:
            search_url = text[0]
            try:
                search, created = Search.objects.get_or_create(
                    url=search_url,
                    defaults={'name': context.user_data['search_name']}
                )
                db_user.search_set.add(search)
            except ParametersValidationError:
                reply_text = "Your URL don't pass validation. Check does URL origin matches \"mobile.de\"."
                status = SA_ENTERING_URL
            else:
                reply_text = "Successfully added."
                status = ConversationHandler.END

    update.message.reply_text(reply_text)
    return status


def sa_show_list(update: Update, context: CallbackContext) -> int:
    db_user = context.django_user

    def format_search(search: Search):
        text = f'{search.pk} - {search.name}'
        return text

    if query := update.callback_query:
        try:
            current_page_num = int(query.data[3:])
        except ValueError:
            current_page_num = 1
    else:
        current_page_num = 1

    searches = Search.objects.exclude(pk__in=db_user.search_set.values_list('pk', flat=True)).order_by('pk')
    searches_count = searches.count()

    if searches_count == 0:
        query.edit_message_text('You already added all Searches to favorites.')
        return ConversationHandler.END
    else:
        text, reply_markup = generate_searches_view(
            searches,
            current_page_num,
            pagination_callback_data_pattern="sa_{}"
        )

        if not query:
            update.message.reply_text(text, reply_markup=reply_markup)
        else:
            query.edit_message_text(text, reply_markup=reply_markup)

        return SA_SHOWING_LIST


def sa_num_input(update: Update, context: CallbackContext) -> int:
    db_user = context.django_user
    text = update.message.text.strip()

    try:
        num = int(text)
    except ValueError:
        reply_text = 'Input is not a number. Try again.'
        status = SA_SHOWING_LIST
    else:
        try:
            search = Search.objects.exclude(pk__in=db_user.search_set.values_list('pk', flat=True)).get(pk=num)
            db_user.search_set.add(search)
        except Search.DoesNotExist:
            reply_text = 'Search with this ID not exists. Try another number.'
            status = SA_SHOWING_LIST
        else:
            reply_text = "Successfully added."
            status = ConversationHandler.END

    update.message.reply_text(reply_text)
    return status


def sa_abort(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('Aborted', reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


########################################################################################################################

def search_del(update: Update, context: CallbackContext):
    db_user = context.django_user

    def format_search(search: Search):
        text = f'{search.pk} - {search.name}'
        return text

    if query := update.callback_query:
        try:
            current_page_num = int(query.data[3:])
        except ValueError:
            current_page_num = 1
    else:
        current_page_num = 1

    searches = db_user.search_set.order_by('pk').all()
    searches_count = searches.count()

    if searches_count == 0:
        query.edit_message_text("You don't have any Searches in your favorites.")
        return ConversationHandler.END
    else:
        text, reply_markup = generate_searches_view(
            searches,
            current_page_num,
            pagination_callback_data_pattern="sd_{}"
        )

        if not query:
            update.message.reply_text(text, reply_markup=reply_markup)
        else:
            query.edit_message_text(text, reply_markup=reply_markup)

        return SA_SHOWING_LIST


def notification(update: Update, context: CallbackContext) -> None:
    db_user = context.django_user

    keyboard = [
        [
            InlineKeyboardButton('On', callback_data='notification_on'),
            InlineKeyboardButton('Off', callback_data='notification_off'),
        ],
    ]

    notification_mode = context.user_data['notification_mode']

    update.message.reply_text(
        f'Now notifications is "{"Off" if notification_mode.endswith("off") else "On"}". Choose notification mode:',
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


def notification_choice(update: Update, context: CallbackContext) -> None:
    db_user = context.django_user

    query = update.callback_query
    query.answer()
    notification_mode = query.data
    context.user_data['notification_mode'] = notification_mode
    query.edit_message_text(text=f'Notification mode is "{"Off" if notification_mode.endswith("off") else "On"}" now.')


def get_updates(update: Update, context: CallbackContext):
    ...


CONTEXT_UPDATERS_GROUP: int = -1


def init_handlers(bot: Bot) -> None:
    # Here take place initialization of handler which adds django_user to callback context
    bot.add_handler(DjangoUserHandler(), group=CONTEXT_UPDATERS_GROUP)

    bot.add_handler(CommandHandler('start', start))

    bot.add_handler(CommandHandler('stop', stop))
    bot.add_handler(CallbackQueryHandler(stop_confirmation, pattern=r'^delete_(?:yes|no)$'))

    bot.add_handler(CommandHandler('help', help_command))

    bot.add_handler(CommandHandler('search_list', search_list))
    bot.add_handler(CallbackQueryHandler(search_list, pattern=r'^sl_\d+$'))

    search_add_handler = ConversationHandler(
        entry_points=[CommandHandler('search_add', sa_choose_input_type)],
        states={
            SA_CHOOSING_INPUT_TYPE: [
                CallbackQueryHandler(
                    sa_show_list,
                    pattern=r'^sa_choose$',
                ),
                CallbackQueryHandler(
                    sa_tmp,
                    pattern=r'^sa_create$',
                ),
            ],
            SA_ENTERING_NAME: [MessageHandler(Filters.text & ~Filters.regex(r'^Abort$'), sa_name_input)],
            SA_ENTERING_URL: [MessageHandler(Filters.text & ~Filters.regex(r'^Abort$'), sa_url_input)],
            SA_SHOWING_LIST: [
                MessageHandler(Filters.text & ~Filters.regex(r'^Abort$'), sa_num_input),
                CallbackQueryHandler(sa_show_list, pattern=r'^sa_\d+$')
            ],
        },
        fallbacks=[MessageHandler(Filters.regex(r'^Abort$'), sa_abort)],
        name='search_add_conversation',
        persistent=True
    )

    bot.add_handler(search_add_handler)

    bot.add_handler(CommandHandler('notification', notification))
    bot.add_handler(CallbackQueryHandler(notification_choice, pattern=r'^notification_(?:on|off)$'))


def main() -> None:
    """Run the bot."""

    tg_bot = Bot()

    init_handlers(tg_bot)

    # Start the Bot
    tg_bot.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    tg_bot.idle()


class Command(BaseCommand):
    help = 'Starts Telegram bot polling'

    def handle(self, *args, **options):
        main()
