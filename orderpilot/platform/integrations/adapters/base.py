"""ERP 适配器接口。

适配器只负责和外部系统之间的数据转换，统一输出/输入 DTO；
DTO 到本地模型的落库由各领域模块注册的同步处理器（sync_handlers）负责，适配器不直接操作 ORM。
"""

import datetime
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class PartnerDTO:
    kind: str  # "supplier" / "customer"
    external_id: str
    code: str
    name: str
    contact_name: str = ""
    phone: str = ""
    email: str = ""
    lead_time_days: int | None = None
    currency: str = ""
    is_active: bool = True


@dataclass
class ProductDTO:
    external_id: str
    part_no: str
    name: str
    name_ja: str = ""
    jan_code: str = ""
    carton_qty: int = 1
    is_active: bool = True
    default_supplier_code: str = ""


@dataclass
class PurchaseOrderLineDTO:
    product_external_id: str
    part_no: str
    quantity: int
    unit_price: Decimal | None = None


@dataclass
class PurchaseOrderDTO:
    number: str
    supplier_external_id: str
    order_date: datetime.date
    required_date: datetime.date | None
    lines: list[PurchaseOrderLineDTO] = field(default_factory=list)


@dataclass
class ExternalRefDTO:
    system: str
    external_id: str
    external_number: str = ""


class ERPAdapter(ABC):
    system: str = ""

    @abstractmethod
    def pull_partners(self, since: datetime.datetime | None = None) -> Iterable[PartnerDTO]: ...

    @abstractmethod
    def pull_products(self, since: datetime.datetime | None = None) -> Iterable[ProductDTO]: ...

    @abstractmethod
    def push_purchase_order(self, po: PurchaseOrderDTO) -> ExternalRefDTO: ...

    def health_check(self) -> bool:
        return True
