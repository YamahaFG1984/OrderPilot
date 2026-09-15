"""ERP 主数据落库：把适配器输出的 DTO 按 ExternalRef（或业务编码）匹配后新增/更新。重复执行是幂等的。"""

from collections import Counter

from orderpilot.platform.extensions.registry import sync_handlers
from orderpilot.platform.integrations.services import find_by_ref, link_ref

from .models import Customer, Product, Supplier


def _upsert(model, system, external_id, lookup, fields, stats, label):
    obj = find_by_ref(model, system, external_id) or model.objects.filter(**lookup).first()
    values = {**lookup, **fields}
    if obj is None:
        obj = model.objects.create(**values)
        stats[f"{label}新增"] += 1
    else:
        changed = [k for k, v in values.items() if getattr(obj, k) != v]
        if changed:
            for k in changed:
                setattr(obj, k, values[k])
            obj.save()
            stats[f"{label}更新"] += 1
        else:
            stats[f"{label}未变"] += 1
    link_ref(obj, system, external_id, next(iter(lookup.values())))
    return obj


@sync_handlers.register("pull:masterdata")
def pull_masterdata(adapter, job):
    stats = Counter()
    for dto in adapter.pull_partners():
        if dto.kind == "supplier":
            fields = {
                "name": dto.name,
                "contact_name": dto.contact_name,
                "phone": dto.phone,
                "email": dto.email,
                "is_active": dto.is_active,
            }
            if dto.lead_time_days:
                fields["lead_time_days"] = dto.lead_time_days
            _upsert(Supplier, adapter.system, dto.external_id, {"code": dto.code}, fields, stats, "供应商")
        else:
            fields = {"name": dto.name, "is_active": dto.is_active}
            if dto.currency:
                fields["currency"] = dto.currency
            _upsert(Customer, adapter.system, dto.external_id, {"code": dto.code}, fields, stats, "客户")

    for dto in adapter.pull_products():
        supplier = (
            Supplier.objects.filter(code=dto.default_supplier_code).first()
            if dto.default_supplier_code
            else None
        )
        fields = {
            "name": dto.name,
            "name_ja": dto.name_ja,
            "jan_code": dto.jan_code,
            "carton_qty": dto.carton_qty,
            "status": Product.Status.ACTIVE if dto.is_active else Product.Status.DISCONTINUED,
            "default_supplier": supplier,
        }
        _upsert(Product, adapter.system, dto.external_id, {"part_no": dto.part_no}, fields, stats, "商品")
    return dict(stats)
