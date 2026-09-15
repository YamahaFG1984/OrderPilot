from datetime import timedelta

from django.utils import timezone

from orderpilot.platform.alerts.engine import scan
from orderpilot.platform.alerts.models import Alert, AlertRule
from orderpilot.platform.notifications.models import Notification
from orderpilot.trade.purchasing.models import PurchaseOrder


def _confirmed(make_po, run, staff, sup_a, today, promised_in=5):
    po = make_po()
    run(po, "submit", staff)
    run(po, "confirm", sup_a, promised_date=today + timedelta(days=promised_in))
    return po


def test_overdue_alert_opens_dedups_and_auto_resolves(make_po, run, staff, sup_a, today):
    po = _confirmed(make_po, run, staff, sup_a, today)
    PurchaseOrder.objects.filter(pk=po.pk).update(promised_date=today - timedelta(days=2))

    stats = scan()
    alert = Alert.objects.get(rule__code="po_overdue")
    assert "逾期 2 天" in alert.title
    assert stats["opened"] >= 1
    assert Notification.objects.filter(recipient=staff, kind="alert.opened").exists()

    scan()
    assert Alert.objects.filter(rule__code="po_overdue").exclude(status="resolved").count() == 1

    PurchaseOrder.objects.filter(pk=po.pk).update(promised_date=today + timedelta(days=10))
    scan()
    alert.refresh_from_db()
    assert alert.status == Alert.Status.RESOLVED


def test_confirm_overdue_alert(make_po, run, staff):
    po = make_po()
    run(po, "submit", staff)
    PurchaseOrder.objects.filter(pk=po.pk).update(submitted_at=timezone.now() - timedelta(days=3))
    scan()
    assert Alert.objects.filter(rule__code="po_confirm_overdue", object_id=po.pk).exists()


def test_milestone_overdue_alert_per_milestone(make_po, run, staff, sup_a, today):
    po = _confirmed(make_po, run, staff, sup_a, today, promised_in=20)
    po.milestones.filter(kind__in=["material", "start"]).update(planned_date=today - timedelta(days=1))
    scan()
    assert Alert.objects.filter(rule__code="po_milestone_overdue").count() == 2


def test_disabled_rule_resolves_its_alerts(make_po, run, staff, sup_a, today):
    po = _confirmed(make_po, run, staff, sup_a, today, promised_in=30)
    scan()
    assert Alert.objects.filter(rule__code="po_promised_late", object_id=po.pk).exists()

    AlertRule.objects.filter(code="po_promised_late").update(enabled=False)
    scan()
    assert not Alert.objects.filter(rule__code="po_promised_late").exclude(status="resolved").exists()
