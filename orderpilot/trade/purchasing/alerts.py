"""采购跟单的内置预警规则。阈值等参数可在后台「预警规则」中调整。"""

from datetime import timedelta

from django.utils import timezone

from orderpilot.platform.alerts.evaluators import AlertCandidate, Evaluator
from orderpilot.platform.alerts.models import Severity
from orderpilot.platform.extensions.registry import alert_evaluators

from .models import ACTIVE_STATUSES, Milestone, POStatus, PurchaseOrder


def _pos():
    return PurchaseOrder.objects.select_related("supplier", "owner").with_summary()


def _candidate(po, title, message="", key=""):
    return AlertCandidate(
        obj=po, title=title, message=message, url=po.get_absolute_url(), recipients=[po.owner], key=key
    )


@alert_evaluators.register("po_confirm_overdue")
class ConfirmOverdue(Evaluator):
    default_name = "供应商超时未确认"
    description = "采购单提交后超过 N 天，供应商仍未确认交期"
    default_severity = Severity.WARNING
    default_params = {"days": 2}

    def evaluate(self, params):
        now = timezone.now()
        cutoff = now - timedelta(days=params["days"])
        for po in _pos().filter(status=POStatus.PENDING_CONFIRM, submitted_at__lt=cutoff):
            days = (now - po.submitted_at).days
            yield _candidate(
                po,
                f"{po.number} 已提交 {days} 天，{po.supplier.name} 仍未确认交期",
                "请联系供应商确认交期，或由跟单员在系统中代为录入。",
            )


@alert_evaluators.register("po_overdue")
class Overdue(Evaluator):
    default_name = "交期已逾期"
    description = "跟进中的采购单已超过承诺交期（未确认时按要求交期）"
    default_severity = Severity.CRITICAL

    def evaluate(self, params):
        today = timezone.localdate()
        for po in _pos().filter(status__in=ACTIVE_STATUSES, expected__lt=today):
            basis = "承诺交期" if po.promised_date else "要求交期"
            yield _candidate(
                po,
                f"{po.number} 已逾期 {(today - po.expected).days} 天（{basis} {po.expected:%m-%d}）",
                f"供应商：{po.supplier.name}；当前状态：{po.get_status_display()}",
            )


@alert_evaluators.register("po_due_soon")
class DueSoon(Evaluator):
    default_name = "交期临近"
    description = "生产中或待验货的采购单，N 天内到达承诺交期"
    default_severity = Severity.WARNING
    default_params = {"days": 3}

    def evaluate(self, params):
        today = timezone.localdate()
        horizon = today + timedelta(days=params["days"])
        statuses = (POStatus.IN_PRODUCTION, POStatus.PENDING_INSPECTION)
        for po in _pos().filter(status__in=statuses, expected__gte=today, expected__lte=horizon):
            days = (po.expected - today).days
            when = "今天到期" if days == 0 else f"还有 {days} 天到期"
            yield _candidate(
                po,
                f"{po.number} {when}（{po.get_status_display()}）",
                f"供应商：{po.supplier.name}；交期 {po.expected:%Y-%m-%d}",
            )


@alert_evaluators.register("po_promised_late")
class PromisedLate(Evaluator):
    default_name = "承诺交期晚于要求交期"
    description = "供应商承诺的交期晚于客户要求的交期"
    default_severity = Severity.WARNING

    def evaluate(self, params):
        for po in _pos().filter(status__in=ACTIVE_STATUSES, promised_date__isnull=False):
            delay = po.promised_delay_days
            if delay and delay > 0:
                yield _candidate(
                    po,
                    f"{po.number} 承诺交期晚于要求交期 {delay} 天",
                    f"要求 {po.required_date:%Y-%m-%d}，供应商承诺 {po.promised_date:%Y-%m-%d}",
                )


@alert_evaluators.register("po_milestone_overdue")
class MilestoneOverdue(Evaluator):
    default_name = "生产节点逾期"
    description = "生产中的采购单，某个节点超过计划日期仍未完成"
    default_severity = Severity.WARNING
    default_params = {"grace_days": 0}

    def evaluate(self, params):
        cutoff = timezone.localdate() - timedelta(days=params["grace_days"])
        qs = Milestone.objects.filter(
            po__status=POStatus.IN_PRODUCTION, actual_date__isnull=True, planned_date__lt=cutoff
        ).select_related("po__supplier", "po__owner")
        for m in qs:
            kind = m.get_kind_display()
            yield _candidate(
                m.po,
                f"{m.po.number}「{kind}」计划 {m.planned_date:%m-%d}，已超期 {m.overdue_days} 天",
                f"供应商：{m.po.supplier.name}",
                key=m.kind,
            )
