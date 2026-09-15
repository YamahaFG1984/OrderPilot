from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class WorkbenchConfig(AppConfig):
    name = "orderpilot.workbench"
    label = "workbench"
    verbose_name = _("内部工作台")
