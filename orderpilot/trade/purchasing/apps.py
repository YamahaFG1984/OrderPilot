from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PurchasingConfig(AppConfig):
    name = "orderpilot.trade.purchasing"
    label = "purchasing"
    verbose_name = _("采购跟单")

    def ready(self):
        # 注册状态机处理器、预警规则、ERP 推送处理器和事件订阅
        from . import alerts, erp, subscribers, workflow  # noqa: F401
