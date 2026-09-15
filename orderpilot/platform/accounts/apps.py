from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AccountsConfig(AppConfig):
    name = "orderpilot.platform.accounts"
    label = "accounts"
    verbose_name = _("账号与权限")
