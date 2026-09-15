from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ShippingConfig(AppConfig):
    name = "orderpilot.trade.shipping"
    label = "shipping"
    verbose_name = _("出货")
