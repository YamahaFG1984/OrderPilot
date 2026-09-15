from django.db import models
from django.utils.translation import gettext_lazy as _

from orderpilot.platform.base_models import TimeStampedModel


class Supplier(TimeStampedModel):
    code = models.CharField(_("供应商编码"), max_length=32, unique=True)
    name = models.CharField(_("名称"), max_length=200)
    contact_name = models.CharField(_("联系人"), max_length=64, blank=True)
    phone = models.CharField(_("电话"), max_length=32, blank=True)
    email = models.EmailField(_("邮箱"), blank=True)
    lead_time_days = models.PositiveIntegerField(_("标准生产周期（天）"), default=30)
    is_active = models.BooleanField(_("启用"), default=True)
    extra = models.JSONField(_("扩展字段"), default=dict, blank=True)

    class Meta:
        verbose_name = _("供应商")
        verbose_name_plural = _("供应商")
        ordering = ["code"]

    def __str__(self):
        return self.name


class Customer(TimeStampedModel):
    code = models.CharField(_("客户编码"), max_length=32, unique=True)
    name = models.CharField(_("名称"), max_length=200)
    currency = models.CharField(_("结算币种"), max_length=3, default="JPY")
    is_active = models.BooleanField(_("启用"), default=True)
    extra = models.JSONField(_("扩展字段"), default=dict, blank=True)

    class Meta:
        verbose_name = _("客户")
        verbose_name_plural = _("客户")
        ordering = ["code"]

    def __str__(self):
        return self.name


class Product(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", _("在售")
        DISCONTINUED = "discontinued", _("废番")

    part_no = models.CharField(_("品番"), max_length=64, unique=True)
    name = models.CharField(_("品名"), max_length=200)
    name_ja = models.CharField(_("日文品名"), max_length=200, blank=True)
    jan_code = models.CharField(_("JAN 码"), max_length=13, blank=True)
    carton_qty = models.PositiveIntegerField(_("箱入数"), default=1)
    status = models.CharField(_("状态"), max_length=16, choices=Status.choices, default=Status.ACTIVE)
    default_supplier = models.ForeignKey(
        Supplier,
        verbose_name=_("默认供应商"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="products",
    )
    extra = models.JSONField(_("扩展字段"), default=dict, blank=True)

    class Meta:
        verbose_name = _("商品")
        verbose_name_plural = _("商品")
        ordering = ["part_no"]

    def __str__(self):
        return f"{self.part_no} {self.name}"

    @property
    def is_discontinued(self):
        return self.status == self.Status.DISCONTINUED
