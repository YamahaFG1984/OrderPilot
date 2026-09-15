"""行级隔离：供应商只能看到、操作自己的采购单和附件。"""

from django.core.files.base import ContentFile
from django.urls import reverse

from orderpilot.platform.attachments.models import Attachment
from orderpilot.platform.attachments.services import add_attachment
from orderpilot.trade.purchasing.models import POStatus


def test_portal_detail_of_other_supplier_is_404(client, make_po, run, staff, supplier_b, sup_a):
    po_b = make_po(supplier=supplier_b)
    run(po_b, "submit", staff)
    client.force_login(sup_a)
    assert client.get(reverse("portal:po_detail", args=[po_b.pk])).status_code == 404
    resp = client.post(
        reverse("portal:po_transition", args=[po_b.pk, "confirm"]), {"promised_date": "2030-01-01"}
    )
    assert resp.status_code == 404
    po_b.refresh_from_db()
    assert po_b.status == POStatus.PENDING_CONFIRM


def test_portal_home_lists_only_own_and_hides_drafts(client, make_po, run, staff, supplier_b, sup_a):
    own = make_po()
    run(own, "submit", staff)
    own_draft = make_po()
    other = make_po(supplier=supplier_b)
    run(other, "submit", staff)

    client.force_login(sup_a)
    html = client.get(reverse("portal:home")).content.decode()
    assert own.number in html
    assert own_draft.number not in html
    assert other.number not in html


def test_supplier_is_redirected_away_from_workbench(client, sup_a):
    client.force_login(sup_a)
    resp = client.get(reverse("workbench:dashboard"))
    assert resp.status_code == 302 and resp.url == reverse("portal:home")


def test_attachment_download_respects_supplier(client, make_po, run, staff, supplier_b, sup_a, sup_b):
    po_b = make_po(supplier=supplier_b)
    run(po_b, "submit", staff)
    att = add_attachment(po_b, ContentFile(b"secret", name="invoice.pdf"), Attachment.Kind.INVOICE, staff)
    url = reverse("attachments:download", args=[att.pk])

    client.force_login(sup_a)
    assert client.get(url).status_code == 404
    client.force_login(sup_b)
    assert client.get(url).status_code == 200


def test_portal_confirm_flow(client, make_po, run, staff, sup_a, today):
    po = make_po()
    run(po, "submit", staff)
    client.force_login(sup_a)
    resp = client.post(
        reverse("portal:po_transition", args=[po.pk, "confirm"]), {"promised_date": today.isoformat()}
    )
    assert resp.status_code == 302
    po.refresh_from_db()
    assert po.status == POStatus.IN_PRODUCTION


def test_portal_hides_customer_and_internal_note(client, make_po, run, staff, sup_a):
    po = make_po()
    po.internal_note = "内部毛利很低"
    po.save()
    run(po, "submit", staff)
    client.force_login(sup_a)
    html = client.get(reverse("portal:po_detail", args=[po.pk])).content.decode()
    assert "内部毛利很低" not in html
    assert po.customer.name not in html
