from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class NotificationsConfig(AppConfig):
    name = "orderpilot.platform.notifications"
    label = "notifications"
    verbose_name = _("通知")

    def ready(self):
        from . import channels  # noqa: F401  注册内置渠道
