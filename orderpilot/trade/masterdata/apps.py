from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class MasterdataConfig(AppConfig):
    name = "orderpilot.trade.masterdata"
    label = "masterdata"
    verbose_name = _("主数据")

    def ready(self):
        from . import sync  # noqa: F401  注册 ERP 主数据同步处理器
