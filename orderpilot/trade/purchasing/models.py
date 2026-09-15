from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords

from orderpilot.platform.accounts.scoping import SupplierScopedQuerySet
from orderpilot.platform.base_models import TimeStampedModel


class POStatus(models.TextChoices):
    DRAFT = "draft", _("草稿")
    PENDING_CONFIRM = "pending_confirm", _("待供应商确认")
    IN_PRODUCTION = "in_production", _("生产中")
    PENDING_INSPECTION = "pending_inspection", _("待验货")
    READY_TO_SHIP = "ready_to_ship", _("待出货")
    SHIPPED = "shipped", _("已出货")
    CANCELLED = "cancelled", _("已取消")


# 仍在跟进中的状态（参与交期预警）
ACTIVE_STATUSES = (
    POStatus.PENDING_CONFIRM,
    POStatus.IN_PRODUCTION,
    POStatus.PENDING_INSPECTION,
    POStatus.READY_TO_SHIP,
)
# 可以修改交期、更新生产节点的状态
REPLY_STATUSES = (POStatus.IN_PRODUCTION, POStatus.PENDING_INSPECTION)


class PurchaseOrderQuerySet(SupplierScopedQuerySet):
    def active(self):
        return self.filter(status__in=ACTIVE_STATUSES)

    def visible_to_supplier(self):
        """草稿和提交前就取消的单据不对供应商展示。"""
        return self.exclude(status=POStatus.DRAFT).exclude(
            status=POStatus.CANCELLED, submitted_at__isnull=True
        )

    def with_summary(self):
        return self.annotate(
            total_qty=Sum("lines__quantity"),
            expected=Coalesce("promised_date", "required_date"),
        )


class PurchaseOrder(TimeStampedModel):
    number = models.CharField(_("采购单号"), max_length=32, unique=True, editable=False)
    supplier = models.ForeignKey(
        "masterdata.Supplier",
        verbose_name=_("供应商"),
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )
    customer = models.ForeignKey(
        "masterdata.Customer",
        verbose_name=_("客户"),
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("跟单员"),
        on_delete=models.PROTECT,
        related_name="owned_purchase_orders",
    )
    status = models.CharField(
        _("状态"), max_length=24, choices=POStatus.choices, default=POStatus.DRAFT, db_index=True
    )
    order_date = models.DateField(_("下单日期"), default=timezone.localdate)
    required_date = models.DateField(_("要求交期"))
    promised_date = models.DateField(_("承诺交期"), null=True, blank=True)
    submitted_at = models.DateTimeField(_("提交时间"), null=True, blank=True)
    confirmed_at = models.DateTimeField(_("确认时间"), null=True, blank=True)
    shipped_at = models.DateTimeField(_("出货时间"), null=True, blank=True)
    reject_reason = models.CharField(_("供应商拒绝原因"), max_length=255, blank=True)
    note = models.TextField(_("给供应商的备注"), blank=True)
    internal_note = models.TextField(_("内部备注"), blank=True)
    extra = models.JSONField(_("扩展字段"), default=dict, blank=True)

    history = HistoricalRecords()
    objects = PurchaseOrderQuerySet.as_manager()

    # 附件下载权限由单据声明（见 attachments.views.download）
    attachment_view_perm = "purchasing.view_po"

    class Meta:
        verbose_name = _("采购单")
        verbose_name_plural = _("采购单")
        ordering = ["-created_at"]

    def __str__(self):
        return self.number

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = self._next_number()
        super().save(*args, **kwargs)

    @classmethod
    def _next_number(cls):
        prefix = "PO" + timezone.localdate().strftime("%y%m%d")
        last = (
            cls.objects.filter(number__startswith=prefix)
            .order_by("-number")
            .values_list("number", flat=True)
            .first()
        )
        seq = int(last[len(prefix) :]) + 1 if last else 1
        return f"{prefix}{seq:03d}"

    def get_absolute_url(self):
        return reverse("workbench:po_detail", args=[self.pk])

    def get_portal_url(self):
        return reverse("portal:po_detail", args=[self.pk])

    @property
    def expected_date(self):
        """跟进用的目标日期：有承诺交期用承诺交期，否则用要求交期。"""
        return self.promised_date or self.required_date

    @property
    def days_left(self):
        if self.expected_date is None:
            return None
        return (self.expected_date - timezone.localdate()).days

    @property
    def is_active(self):
        return self.status in ACTIVE_STATUSES

    @property
    def is_overdue(self):
        return self.is_active and self.days_left is not None and self.days_left < 0

    @property
    def promised_delay_days(self):
        if self.promised_date and self.required_date:
            return (self.promised_date - self.required_date).days
        return None


class PurchaseOrderLine(models.Model):
    po = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(
        "masterdata.Product", verbose_name=_("商品"), on_delete=models.PROTECT, related_name="po_lines"
    )
    quantity = models.PositiveIntegerField(_("数量"))
    unit_price = models.DecimalField(_("单价"), max_digits=12, decimal_places=2, null=True, blank=True)
    note = models.CharField(_("备注"), max_length=200, blank=True)

    class Meta:
        verbose_name = _("采购明细")
        verbose_name_plural = _("采购明细")
        ordering = ["id"]

    def __str__(self):
        return f"{self.product.part_no} × {self.quantity}"

    @property
    def amount(self):
        if self.unit_price is None:
            return None
        return self.unit_price * self.quantity

    @property
    def cartons(self):
        carton = self.product.carton_qty or 1
        return self.quantity / carton


class Milestone(models.Model):
    class Kind(models.TextChoices):
        MATERIAL = "material", _("备料完成")
        START = "start", _("开工")
        DONE = "done", _("完工")
        INSPECTION = "inspection", _("验货")

    KIND_ORDER = [Kind.MATERIAL, Kind.START, Kind.DONE, Kind.INSPECTION]

    po = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="milestones")
    kind = models.CharField(_("节点"), max_length=16, choices=Kind.choices)
    seq = models.PositiveSmallIntegerField(default=0)
    planned_date = models.DateField(_("计划日期"), null=True, blank=True)
    actual_date = models.DateField(_("实际日期"), null=True, blank=True)
    note = models.CharField(_("备注"), max_length=200, blank=True)

    class Meta:
        verbose_name = _("生产节点")
        verbose_name_plural = _("生产节点")
        ordering = ["seq"]
        constraints = [models.UniqueConstraint(fields=["po", "kind"], name="uniq_po_milestone_kind")]

    def __str__(self):
        return f"{self.po.number} {self.get_kind_display()}"

    @property
    def overdue_days(self):
        if self.actual_date or not self.planned_date:
            return 0
        return max((timezone.localdate() - self.planned_date).days, 0)


class DeliveryDateChange(models.Model):
    """交期变更历史：和供应商对账、判定罚款的依据。"""

    po = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="date_changes")
    old_date = models.DateField(_("原交期"), null=True, blank=True)
    new_date = models.DateField(_("新交期"))
    reason = models.CharField(_("原因"), max_length=255)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_("变更人"), null=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(_("时间"), auto_now_add=True)

    class Meta:
        verbose_name = _("交期变更")
        verbose_name_plural = _("交期变更")
        ordering = ["-created_at", "-id"]

    @property
    def delta_days(self):
        if self.old_date:
            return (self.new_date - self.old_date).days
        return None
