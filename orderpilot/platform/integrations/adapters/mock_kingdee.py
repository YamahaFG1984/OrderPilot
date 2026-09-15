"""模拟金蝶云星空适配器。

从本地 JSON 读取「金蝶风格」的原始数据（字段名沿用 FNumber / FName / FForbidStatus，
客户自定义字段以 F_ 开头），演示真实适配器要做的字段映射工作。
拿到测试账套后，新增一个真正调用 WebAPI 的适配器替换即可，下游代码不需要改。
"""

import hashlib
import json
from pathlib import Path

from .base import ERPAdapter, ExternalRefDTO, PartnerDTO, ProductDTO, PurchaseOrderDTO

DATA_FILE = Path(__file__).parent / "mock_data" / "kingdee_demo.json"


class MockKingdeeAdapter(ERPAdapter):
    system = "kingdee"

    def __init__(self, data_file=DATA_FILE):
        self._data = json.loads(Path(data_file).read_text(encoding="utf-8"))

    # ---- 拉取 ----
    def pull_partners(self, since=None):
        for row in self._data.get("BD_Supplier", []):
            yield PartnerDTO(
                kind="supplier",
                external_id=str(row["FSupplierId"]),
                code=row["FNumber"],
                name=row["FName"],
                contact_name=row.get("FContact", ""),
                phone=row.get("FTel", ""),
                email=row.get("FEmail", ""),
                lead_time_days=row.get("F_LeadTime"),
                is_active=row.get("FForbidStatus", "A") == "A",
            )
        for row in self._data.get("BD_Customer", []):
            yield PartnerDTO(
                kind="customer",
                external_id=str(row["FCUSTID"]),
                code=row["FNumber"],
                name=row["FName"],
                currency=row.get("FCurrency", "JPY"),
                is_active=row.get("FForbidStatus", "A") == "A",
            )

    def pull_products(self, since=None):
        for row in self._data.get("BD_MATERIAL", []):
            yield ProductDTO(
                external_id=str(row["FMATERIALID"]),
                part_no=row["FNumber"],
                name=row["FName"],
                name_ja=row.get("F_NameJa", ""),
                jan_code=row.get("FBARCODE", ""),
                carton_qty=int(row.get("F_CartonQty") or 1),
                is_active=row.get("FForbidStatus", "A") == "A",  # 金蝶禁用 = 废番
                default_supplier_code=row.get("F_DefaultSupplier", ""),
            )

    # ---- 推送 ----
    def push_purchase_order(self, po: PurchaseOrderDTO) -> ExternalRefDTO:
        # 模拟金蝶「采购订单」保存接口：返回内码和单据编号
        digest = int(hashlib.sha1(po.number.encode()).hexdigest()[:8], 16)
        return ExternalRefDTO(
            system=self.system,
            external_id=str(500000 + digest % 100000),
            external_number=f"CGDD{po.order_date:%Y%m}{digest % 10000:04d}",
        )
