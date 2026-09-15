"""页面冒烟测试：主要页面能正常渲染，新建采购单表单能保存。"""

from datetime import timedelta

import pytest
from django.urls import reverse

from orderpilot.trade.purchasing.models import PurchaseOrder


@pytest.fixture
def po_in_production(make_po, run, staff, sup_a, today):
    po = make_po()
    run(po, "submit", staff)
    run(po, "confirm", sup_a, promised_date=today + timedelta(days=8))
    return po


@pytest.mark.parametrize(
    "name",
    ["workbench:dashboard", "workbench:po_list", "workbench:po_create", "workbench:alerts", "workbench:sync"],
)
def test_workbench_pages_render(client, staff, po_in_production, name):
    client.force_login(staff)
    assert client.get(reverse(name)).status_code == 200


def test_po_detail_renders_for_both_sides(client, staff, sup_a, po_in_production):
    client.force_login(staff)
    assert client.get(reverse("workbench:po_detail", args=[po_in_production.pk])).status_code == 200
    client.force_login(sup_a)
    resp = client.get(reverse("portal:po_detail", args=[po_in_production.pk]))
    assert resp.status_code == 200
    assert "修改交期" in resp.content.decode()


def test_notifications_page_renders_for_both_sides(client, staff, sup_a):
    for user in (staff, sup_a):
        client.force_login(user)
        assert client.get(reverse("notifications:list")).status_code == 200


def test_create_po_via_form(client, staff, supplier_a, customer, product, today):
    client.force_login(staff)
    data = {
        "supplier": supplier_a.pk,
        "customer": customer.pk,
        "owner": staff.pk,
        "order_date": today.isoformat(),
        "required_date": (today + timedelta(days=30)).isoformat(),
        "note": "",
        "internal_note": "",
        "lines-TOTAL_FORMS": "3",
        "lines-INITIAL_FORMS": "0",
        "lines-MIN_NUM_FORMS": "1",
        "lines-MAX_NUM_FORMS": "1000",
        "lines-0-product": product.pk,
        "lines-0-quantity": "240",
        "lines-0-unit_price": "6.80",
    }
    resp = client.post(reverse("workbench:po_create"), data)
    assert resp.status_code == 302, resp.content.decode()[:2000]
    po = PurchaseOrder.objects.get()
    assert po.lines.get().quantity == 240
    assert po.number.startswith("PO")
