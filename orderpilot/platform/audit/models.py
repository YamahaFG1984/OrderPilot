from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils.translation import gettext_lazy as _


class ActivityLog(models.Model):
    """业务操作日志：状态转换、交期变更、上传附件等，用于单据时间线和追溯。"""

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_("操作人"), null=True, blank=True, on_delete=models.SET_NULL
    )
    verb = models.CharField(_("动作"), max_length=64)
    message = models.CharField(_("说明"), max_length=255)
    data = models.JSONField(_("数据"), default=dict, blank=True, encoder=DjangoJSONEncoder)
    created_at = models.DateTimeField(_("时间"), auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("操作日志")
        verbose_name_plural = _("操作日志")
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.actor or '系统'} {self.message}"
