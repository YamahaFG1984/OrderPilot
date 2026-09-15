from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class IntegrationsConfig(AppConfig):
    name = "orderpilot.platform.integrations"
    label = "integrations"
    verbose_name = _("ERP 集成")
