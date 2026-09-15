from datetime import timedelta

import pytest
from django.core import mail
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile

from orderpilot.platform.attachments.models import Attachment
from orderpilot.platform.attachments.services import add_attachment
from orderpilot.platform.integrations.models import SyncJob
from orderpilot.platform.integrations.services import ref_for
from orderpilot.platform.notifications.models import Notification
from orderpilot.platform.workflow.engine import TransitionError
from orderpilot.trade.purchasing.models import POStatus
from orderpilot.trade.purchasing.services import change_promised_date


def test_full_flow_from_draft_to_shipped(make_po, run, staff, sup_a, today):
    po = make_po()
    run(po, "submit", staff)
    assert po.status == POStatus.PENDING_CONFIRM and po.submitted_at

    promised = today + timedelta(days=15)
    run(po, "confirm", sup_a, promised_date=promised)
    assert po.status == POStatus.IN_PRODUCTION
    assert po.promised_date == promised
    assert po.milestones.count() == 4
    assert po.date_changes.count() == 1

    run(po, "finish_production", sup_a)
    run(po, "pass_inspection", staff)
    assert po.status == POStatus.READY_TO_SHIP

    # 演示扩展（extensions.demo_jp）要求出货前必须上传装箱单
    with pytest.raises(TransitionError, match="装箱单"):
        run(po, "ship", staff, ship_date=today)
    add_attachment(po, ContentFile(b"pl", name="packing.pdf"), Attachment.Kind.PACKING_LIST, sup_a)
    run(po, "ship", staff, ship_date=today, tracking_no="TRK001")
    assert po.status == POStatus.SHIPPED
    assert po.shipments.get().tracking_no == "TRK001"


def test_supplier_cannot_run_internal_transitions(make_po, run, sup_a):
    po = make_po()
    with pytest.raises(PermissionDenied):
        run(po, "submit", sup_a)


def test_other_supplier_cannot_confirm(make_po, run, staff, sup_b, today):
    po = make_po()
    run(po, "submit", staff)
    with pytest.raises(PermissionDenied):
        run(po, "confirm", sup_b, promised_date=today)


def test_internal_can_confirm_on_behalf_of_supplier(make_po, run, staff, today):
    po = make_po()
    run(po, "submit", staff)
    run(po, "confirm", staff, promised_date=today + timedelta(days=5))
    assert po.status == POStatus.IN_PRODUCTION


def test_wrong_state_is_rejected(make_po, run, sup_a, today):
    po = make_po()
    with pytest.raises(TransitionError):
        run(po, "confirm", sup_a, promised_date=today)


def test_discontinued_product_blocks_submit(make_po, run, staff, discontinued):
    po = make_po(item=discontinued)
    with pytest.raises(TransitionError, match="废番"):
        run(po, "submit", staff)
    po.refresh_from_db()
    assert po.status == POStatus.DRAFT


def test_confirm_rejects_past_date(make_po, run, staff, sup_a, today):
    po = make_po()
    run(po, "submit", staff)
    with pytest.raises(TransitionError):
        run(po, "confirm", sup_a, promised_date=today - timedelta(days=1))


def test_reject_requires_reason_and_returns_to_draft(make_po, run, staff, sup_a):
    po = make_po()
    run(po, "submit", staff)
    with pytest.raises(TransitionError):
        run(po, "reject", sup_a)
    run(po, "reject", sup_a, reason="原料涨价，需重新报价")
    assert po.status == POStatus.DRAFT
    assert po.reject_reason == "原料涨价，需重新报价"


def test_submit_notifies_supplier_and_pushes_to_erp(
    make_po, run, staff, sup_a, sup_b, django_capture_on_commit_callbacks
):
    po = make_po()
    with django_capture_on_commit_callbacks(execute=True):
        run(po, "submit", staff)

    assert Notification.objects.filter(recipient=sup_a, kind="po.submitted").exists()
    assert not Notification.objects.filter(recipient=sup_b).exists()
    assert any(po.number in m.subject for m in mail.outbox)

    job = SyncJob.objects.get(entity="purchase_order")
    assert job.status == SyncJob.Status.SUCCESS
    assert ref_for(po).external_number.startswith("CGDD")


def test_supplier_date_change_is_recorded_and_notifies_owner(
    make_po, run, staff, sup_a, today, django_capture_on_commit_callbacks
):
    po = make_po()
    run(po, "submit", staff)
    run(po, "confirm", sup_a, promised_date=today + timedelta(days=10))
    with django_capture_on_commit_callbacks(execute=True):
        change_promised_date(po, sup_a, today + timedelta(days=13), "原料延迟")

    change = po.date_changes.first()
    assert change.delta_days == 3 and change.reason == "原料延迟"
    assert Notification.objects.filter(recipient=staff, kind="po.date_changed").exists()


def test_date_change_not_allowed_before_confirm(make_po, run, staff, sup_a, today):
    po = make_po()
    run(po, "submit", staff)
    with pytest.raises(TransitionError):
        change_promised_date(po, sup_a, today, "x")
