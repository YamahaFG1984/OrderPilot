from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AttachmentsConfig(AppConfig):
    name = "orderpilot.platform.attachments"
    label = "attachments"
    verbose_name = _("附件")
