from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PortalConfig(AppConfig):
    name = "orderpilot.portal"
    label = "portal"
    verbose_name = _("供应商门户")
