from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from telegram_bot import bot
from .managers import TelegramUserManager


class TelegramUser(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(
        _('username'),
        max_length=150,
        unique=True,
        help_text=_('Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.'),
        error_messages={
            'unique': _("A user with that username already exists."),
        },
    )
    first_name = models.CharField(_('first name'), max_length=150, blank=True)
    last_name = models.CharField(_('last name'), max_length=150, blank=True)
    is_staff = models.BooleanField(
        _('staff status'),
        default=False,
        help_text=_('Designates whether the user can log into this admin site.'),
    )
    is_active = models.BooleanField(
        _('active'),
        default=True,
        help_text=_(
            'Designates whether this user should be treated as active. '
            'Unselect this instead of deleting accounts.'),
    )
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)
    _photo_url = models.URLField(_('photo url'), max_length=2048, db_column='photo_url', blank=True)
    telegram_id = models.PositiveIntegerField(_('telegram id'), unique=True, null=True, blank=True)

    objects = TelegramUserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')

    @property
    def photo_url(self):
        return self._photo_url or None

    @photo_url.setter
    def photo_url(self, value):
        self._photo_url = value

    def get_full_name(self):
        """
        Return the first_name plus the last_name, with a space in between.
        """
        full_name = '%s %s' % (self.first_name, self.last_name)
        return full_name.strip()

    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name

    def notify(self, message: str, **kwargs):
        """Send a telegram message via bot to this user."""
        message_parse_mode = kwargs.get('parse_mode') or 'MarkdownV2'
        bot.send_message(self.telegram_id, message, message_parse_mode)
