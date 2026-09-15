from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from orderpilot.platform.audit.services import log_activity
from orderpilot.platform.workflow import events
from orderpilot.platform.workflow.engine import TransitionError

from .models import REPLY_STATUSES, DeliveryDateChange, Milestone


def plan_milestones(po):
    """按承诺交期倒排生产节点的计划日期，已填写的实际日期保留不动。"""
    today = timezone.localdate()
    end = po.promised_date
    span = max((end - today).days, 0)
    plan = {
        Milestone.Kind.MATERIAL: today + timedelta(days=round(span * 0.25)),
        Milestone.Kind.START: today + timedelta(days=round(span * 0.35)),
        Milestone.Kind.DONE: end - timedelta(days=min(2, span)),
        Milestone.Kind.INSPECTION: end,
    }
    for seq, kind in enumerate(Milestone.KIND_ORDER):
        Milestone.objects.update_or_create(
            po=po, kind=kind, defaults={"seq": seq, "planned_date": plan[kind]}
        )


def mark_milestone_done(po, kind):
    Milestone.objects.filter(po=po, kind=kind, actual_date__isnull=True).update(
        actual_date=timezone.localdate()
    )


def _check_reply(po, user):
    if not user.has_perm("purchasing.reply_po", po):
        raise PermissionDenied("没有权限修改这张采购单")
    if po.status not in REPLY_STATUSES:
        raise TransitionError(f"当前状态（{po.get_status_display()}）不能修改交期或生产节点")


def change_promised_date(po, user, new_date, reason):
    _check_reply(po, user)
    old_date = po.promised_date
    if new_date == old_date:
        raise TransitionError("新交期与当前承诺交期相同")
    with transaction.atomic():
        DeliveryDateChange.objects.create(
            po=po, old_date=old_date, new_date=new_date, reason=reason, changed_by=user
        )
        po.promised_date = new_date
        po.save(update_fields=["promised_date", "updated_at"])
        log_activity(
            po,
            "purchasing.po.date_changed",
            f"交期变更：{old_date:%m-%d} → {new_date:%m-%d}" if old_date else f"交期设为 {new_date:%m-%d}",
            actor=user,
            reason=reason,
        )
        events.publish(
            "purchasing.po.date_changed",
            obj=po,
            user=user,
            old_date=old_date,
            new_date=new_date,
            reason=reason,
        )
    return po


def update_milestone(po, milestone_id, user, planned_date=None, actual_date=None):
    _check_reply(po, user)
    milestone = po.milestones.get(pk=milestone_id)
    if actual_date and actual_date > timezone.localdate():
        raise TransitionError("实际日期不能晚于今天")
    with transaction.atomic():
        milestone.planned_date = planned_date
        milestone.actual_date = actual_date
        milestone.save(update_fields=["planned_date", "actual_date"])
        detail = (
            f"实际 {actual_date:%m-%d}"
            if actual_date
            else f"计划 {planned_date:%m-%d}"
            if planned_date
            else "清空日期"
        )
        log_activity(
            po,
            "purchasing.po.milestone_updated",
            f"更新生产节点「{milestone.get_kind_display()}」：{detail}",
            actor=user,
        )
        events.publish("purchasing.po.milestone_updated", obj=po, user=user, milestone=milestone)
    return milestone
