from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from orderpilot.platform.base_models import TimeStampedModel


class Shipment(TimeStampedModel):
    po = models.ForeignKey(
        "purchasing.PurchaseOrder",
        verbose_name=_("采购单"),
        on_delete=models.CASCADE,
        related_name="shipments",
    )
    ship_date = models.DateField(_("出货日期"))
    forwarder = models.CharField(_("货代"), max_length=100, blank=True)
    tracking_no = models.CharField(_("提单号 / 运单号"), max_length=64, blank=True)
    container_no = models.CharField(_("柜号"), max_length=32, blank=True)
    eta = models.DateField(_("预计到港"), null=True, blank=True)
    note = models.CharField(_("备注"), max_length=200, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_("登记人"), null=True, on_delete=models.SET_NULL
    )

    class Meta:
        verbose_name = _("出货记录")
        verbose_name_plural = _("出货记录")
        ordering = ["-ship_date", "-id"]

    def __str__(self):
        return f"{self.po} @ {self.ship_date}"
