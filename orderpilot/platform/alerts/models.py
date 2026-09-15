from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


class Severity(models.TextChoices):
    INFO = "info", _("提示")
    WARNING = "warning", _("警告")
    CRITICAL = "critical", _("严重")


SEVERITY_RANK = {Severity.INFO: 0, Severity.WARNING: 1, Severity.CRITICAL: 2}


class AlertRule(models.Model):
    """预警规则配置。code 对应注册表中的 evaluator，参数和级别可在后台调整。"""

    code = models.CharField(_("规则代码"), max_length=64, unique=True)
    name = models.CharField(_("名称"), max_length=100)
    description = models.CharField(_("说明"), max_length=255, blank=True)
    enabled = models.BooleanField(_("启用"), default=True)
    severity = models.CharField(_("级别"), max_length=16, choices=Severity.choices, default=Severity.WARNING)
    params = models.JSONField(_("参数"), default=dict, blank=True)

    class Meta:
        verbose_name = _("预警规则")
        verbose_name_plural = _("预警规则")
        ordering = ["code"]

    def __str__(self):
        return self.name


class Alert(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", _("待处理")
        ACKNOWLEDGED = "ack", _("已知悉")
        RESOLVED = "resolved", _("已解除")

    rule = models.ForeignKey(
        AlertRule, verbose_name=_("规则"), on_delete=models.CASCADE, related_name="alerts"
    )
    dedup_key = models.CharField(_("去重键"), max_length=200)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    severity = models.CharField(_("级别"), max_length=16, choices=Severity.choices)
    title = models.CharField(_("标题"), max_length=200)
    message = models.TextField(_("说明"), blank=True)
    url = models.CharField(_("链接"), max_length=500, blank=True)
    status = models.CharField(_("状态"), max_length=16, choices=Status.choices, default=Status.OPEN)
    first_seen_at = models.DateTimeField(_("首次触发"), auto_now_add=True)
    last_seen_at = models.DateTimeField(_("最近触发"), auto_now_add=True)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_("知悉人"), null=True, blank=True, on_delete=models.SET_NULL
    )
    acknowledged_at = models.DateTimeField(_("知悉时间"), null=True, blank=True)
    resolved_at = models.DateTimeField(_("解除时间"), null=True, blank=True)

    class Meta:
        verbose_name = _("预警")
        verbose_name_plural = _("预警")
        ordering = ["-first_seen_at"]
        indexes = [models.Index(fields=["content_type", "object_id"])]
        constraints = [
            # 同一个问题在未解除期间只保留一条预警
            models.UniqueConstraint(
                fields=["dedup_key"], condition=~Q(status="resolved"), name="uniq_active_alert_key"
            ),
        ]

    def __str__(self):
        return self.title

    @property
    def rank(self):
        return SEVERITY_RANK.get(self.severity, 0)
