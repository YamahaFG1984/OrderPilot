from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AuditConfig(AppConfig):
    name = "orderpilot.platform.audit"
    label = "audit"
    verbose_name = _("审计日志")
