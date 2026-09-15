from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AlertsConfig(AppConfig):
    name = "orderpilot.platform.alerts"
    label = "alerts"
    verbose_name = _("预警")
