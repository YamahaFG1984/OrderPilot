"""采购单推送到 ERP：OrderPilot 是采购单的权威来源，创建后推送给 ERP 记账。"""

from orderpilot.platform.audit.services import log_activity
from orderpilot.platform.extensions.registry import sync_handlers
from orderpilot.platform.integrations.adapters.base import PurchaseOrderDTO, PurchaseOrderLineDTO
from orderpilot.platform.integrations.services import link_ref, ref_for

from .models import PurchaseOrder


def _external_id(obj, system, fallback):
    ref = ref_for(obj, system)
    return ref.external_id if ref else fallback


@sync_handlers.register("push:purchase_order")
def push_purchase_order(adapter, job):
    po = PurchaseOrder.objects.select_related("supplier").get(pk=job.params["object_id"])
    dto = PurchaseOrderDTO(
        number=po.number,
        supplier_external_id=_external_id(po.supplier, adapter.system, po.supplier.code),
        order_date=po.order_date,
        required_date=po.required_date,
        lines=[
            PurchaseOrderLineDTO(
                product_external_id=_external_id(line.product, adapter.system, line.product.part_no),
                part_no=line.product.part_no,
                quantity=line.quantity,
                unit_price=line.unit_price,
            )
            for line in po.lines.select_related("product")
        ],
    )
    result = adapter.push_purchase_order(dto)
    link_ref(po, result.system, result.external_id, result.external_number)
    log_activity(po, "integrations.erp_pushed", f"已同步到 ERP，采购订单号 {result.external_number}")
    return {"采购单": po.number, "ERP 单号": result.external_number}
