from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _


class Attachment(models.Model):
    class Kind(models.TextChoices):
        PACKING_LIST = "packing_list", _("装箱单")
        INVOICE = "invoice", _("发票")
        INSPECTION = "inspection", _("验货报告")
        CUSTOMS = "customs", _("报关资料")
        OTHER = "other", _("其他")

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    kind = models.CharField(_("类型"), max_length=32, choices=Kind.choices, default=Kind.OTHER)
    file = models.FileField(_("文件"), upload_to="attachments/%Y/%m/")
    original_name = models.CharField(_("文件名"), max_length=255)
    note = models.CharField(_("备注"), max_length=200, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_("上传人"), null=True, on_delete=models.SET_NULL
    )
    uploaded_at = models.DateTimeField(_("上传时间"), auto_now_add=True)

    class Meta:
        verbose_name = _("附件")
        verbose_name_plural = _("附件")
        ordering = ["-uploaded_at"]
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self):
        return self.original_name
