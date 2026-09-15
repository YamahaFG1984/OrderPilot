from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Notification(models.Model):
    """站内信本身。其他渠道（邮件、企业微信等）由分发任务按配置投递。"""

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("收件人"),
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    kind = models.CharField(_("类型"), max_length=64)
    title = models.CharField(_("标题"), max_length=200)
    body = models.TextField(_("正文"), blank=True)
    url = models.CharField(_("链接"), max_length=500, blank=True)
    created_at = models.DateTimeField(_("时间"), auto_now_add=True)
    read_at = models.DateTimeField(_("已读时间"), null=True, blank=True)

    class Meta:
        verbose_name = _("通知")
        verbose_name_plural = _("通知")
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["recipient", "read_at"])]

    def __str__(self):
        return self.title

    @property
    def is_read(self):
        return self.read_at is not None
