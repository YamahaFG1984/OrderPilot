from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _


class ExternalRef(models.Model):
    """本地对象与外部系统（ERP）对象的 ID 映射。业务模型上不直接加 kingdee_id 之类的字段。"""

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    system = models.CharField(_("外部系统"), max_length=32)
    external_id = models.CharField(_("外部 ID"), max_length=64)
    external_number = models.CharField(_("外部编号"), max_length=64, blank=True)
    synced_at = models.DateTimeField(_("最近同步"), auto_now=True)

    class Meta:
        verbose_name = _("外部 ID 映射")
        verbose_name_plural = _("外部 ID 映射")
        constraints = [
            models.UniqueConstraint(
                fields=["system", "content_type", "external_id"], name="uniq_extref_external"
            ),
            models.UniqueConstraint(fields=["system", "content_type", "object_id"], name="uniq_extref_local"),
        ]

    def __str__(self):
        return f"{self.system}:{self.external_number or self.external_id}"


class SyncJob(models.Model):
    class Direction(models.TextChoices):
        PULL = "pull", _("拉取")
        PUSH = "push", _("推送")

    class Status(models.TextChoices):
        PENDING = "pending", _("排队中")
        RUNNING = "running", _("执行中")
        SUCCESS = "success", _("成功")
        FAILED = "failed", _("失败")

    system = models.CharField(_("外部系统"), max_length=32)
    entity = models.CharField(_("数据类型"), max_length=64)
    direction = models.CharField(_("方向"), max_length=8, choices=Direction.choices)
    status = models.CharField(_("状态"), max_length=16, choices=Status.choices, default=Status.PENDING)
    params = models.JSONField(_("参数"), default=dict, blank=True)
    stats = models.JSONField(_("统计"), default=dict, blank=True)
    error = models.TextField(_("错误信息"), blank=True)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_("触发人"), null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(_("创建时间"), auto_now_add=True)
    started_at = models.DateTimeField(_("开始时间"), null=True, blank=True)
    finished_at = models.DateTimeField(_("结束时间"), null=True, blank=True)

    class Meta:
        verbose_name = _("同步任务")
        verbose_name_plural = _("同步任务")
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.get_direction_display()} {self.entity} #{self.pk}"

    @property
    def is_active(self):
        return self.status in (self.Status.PENDING, self.Status.RUNNING)

    @property
    def duration_seconds(self):
        if self.started_at and self.finished_at:
            return round((self.finished_at - self.started_at).total_seconds(), 1)
        return None
