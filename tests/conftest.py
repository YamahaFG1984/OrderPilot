from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from orderpilot.trade.masterdata.models import Customer, Product, Supplier
from orderpilot.trade.purchasing.models import PurchaseOrder, PurchaseOrderLine
from orderpilot.trade.purchasing.workflow import po_workflow


@pytest.fixture
def today():
    return timezone.localdate()


@pytest.fixture
def supplier_a(db):
    return Supplier.objects.create(code="S-A", name="供应商甲")


@pytest.fixture
def supplier_b(db):
    return Supplier.objects.create(code="S-B", name="供应商乙")


@pytest.fixture
def customer(db):
    return Customer.objects.create(code="C-1", name="東京テスト商事")


@pytest.fixture
def product(db, supplier_a):
    return Product.objects.create(
        part_no="P-001", name="纯棉面巾", carton_qty=10, default_supplier=supplier_a
    )


@pytest.fixture
def discontinued(db):
    return Product.objects.create(part_no="P-OLD", name="旧款毛巾", status=Product.Status.DISCONTINUED)


@pytest.fixture
def staff(db):
    return get_user_model().objects.create_user(
        "zhang", "zhang@example.com", "pw", user_type="internal", display_name="张伟"
    )


@pytest.fixture
def sup_a(db, supplier_a):
    return get_user_model().objects.create_user(
        "sup_a", "a@example.com", "pw", user_type="supplier", supplier=supplier_a
    )


@pytest.fixture
def sup_b(db, supplier_b):
    return get_user_model().objects.create_user(
        "sup_b", "b@example.com", "pw", user_type="supplier", supplier=supplier_b
    )


@pytest.fixture
def make_po(db, supplier_a, customer, staff, product, today):
    def _make(supplier=None, required_in=20, qty=100, item=None):
        po = PurchaseOrder.objects.create(
            supplier=supplier or supplier_a,
            customer=customer,
            owner=staff,
            required_date=today + timedelta(days=required_in),
        )
        PurchaseOrderLine.objects.create(po=po, product=item or product, quantity=qty)
        return po

    return _make


@pytest.fixture
def run():
    def _run(po, name, user, **payload):
        return po_workflow.run(po, name, user=user, **payload)

    return _run
