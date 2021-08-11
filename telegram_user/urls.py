from django.urls import path

from .views import TelegramUserOAuthView

urlpatterns = [
    path('telegram_login/', TelegramUserOAuthView.as_view(), name='tg_login')
]
