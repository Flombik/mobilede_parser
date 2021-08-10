import hmac
from collections import OrderedDict
from hashlib import sha256
from typing import Dict

from django.conf import settings
from django.contrib.auth import login as auth_login
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect
from django.views import View
from furl import furl

from ..models import TelegramUser


class TelegramUserOAuthView(View):
    def _check_tg_hash(self) -> bool:
        request = OrderedDict(sorted(self.request.GET.items()))
        received_hash = request.pop('hash')

        generated_hash = hmac.new(
            sha256(settings.TELEGRAM_BOT_TOKEN.encode('utf-8')).digest(),
            msg='\n'.join(f'{key}={value}' for key, value in request.items()).encode('utf-8'),
            digestmod=sha256
        ).hexdigest()

        return received_hash == generated_hash

    def _prepare_user_data(self) -> Dict[str, str]:
        user_data = self.request.GET.dict()
        user_data['telegram_id'] = user_data.pop('id', None)
        user_data.pop('hash', None)
        user_data.pop('auth_date', None)
        return user_data

    def _form_redirect_link(self) -> str:
        referer_url = furl(self.request.headers.get('Referer'))
        redirect_url = furl(scheme=referer_url.scheme, netloc=referer_url.netloc,
                            path=referer_url.query.params.get('next'))
        return str(redirect_url) or '/'

    def get(self, request, *args, **kwargs):
        if self._check_tg_hash():
            user_data = self._prepare_user_data()
            username = user_data.pop('username')

            user, created = TelegramUser.objects.get_or_create(username=username, defaults=user_data)
            if not created:
                for key, value in user_data.items():
                    setattr(user, key, value)
                user.save()

            auth_login(request, user)
            return redirect(self._form_redirect_link())
        else:
            return HttpResponseBadRequest()
