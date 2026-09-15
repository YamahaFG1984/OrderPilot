"""采购单领域事件的订阅：通知相关人员、推送 ERP、刷新预警。全部在事务提交后执行。"""

from django.contrib.auth import get_user_model

from orderpilot.platform.alerts.tasks import scan_alerts
from orderpilot.platform.integrations.services import start_sync
from orderpilot.platform.notifications.services import notify
from orderpilot.platform.workflow import events


def _supplier_users(po, exclude=None):
    users = get_user_model().objects.filter(supplier_id=po.supplier_id, user_type="supplier", is_active=True)
    return [u for u in users if u != exclude]


def _owner(po, exclude=None):
    return [po.owner] if po.owner_id and po.owner != exclude else []


def _reason(kw):
    return (kw.get("payload") or {}).get("reason", "")


@events.subscribe("purchasing.po.submit")
def on_submit(event, obj, user, **kw):
    notify(
        _supplier_users(obj, user),
        "po.submitted",
        f"新采购单 {obj.number} 待确认交期",
        f"要求交期：{obj.required_date:%Y-%m-%d}。请确认交期，或提出拒绝/改单。",
        obj.get_portal_url(),
    )
    start_sync("purchase_order", "push", user=user, object_id=obj.pk)


@events.subscribe("purchasing.po.confirm")
def on_confirm(event, obj, user, **kw):
    body = f"承诺交期：{obj.promised_date:%Y-%m-%d}（要求 {obj.required_date:%Y-%m-%d}）"
    if (obj.promised_delay_days or 0) > 0:
        body += f"，晚于要求 {obj.promised_delay_days} 天，请关注。"
    notify(
        _owner(obj, user),
        "po.confirmed",
        f"{obj.supplier.name} 已确认 {obj.number}",
        body,
        obj.get_absolute_url(),
    )


@events.subscribe("purchasing.po.reject")
def on_reject(event, obj, user, **kw):
    notify(
        _owner(obj, user),
        "po.rejected",
        f"{obj.supplier.name} 拒绝了 {obj.number}",
        f"原因：{_reason(kw)}。采购单已退回草稿，请修改后重新提交。",
        obj.get_absolute_url(),
    )


@events.subscribe("purchasing.po.finish_production")
def on_finish(event, obj, user, **kw):
    notify(
        _owner(obj, user), "po.production_done", f"{obj.number} 已完工，申请验货", "", obj.get_absolute_url()
    )


@events.subscribe("purchasing.po.pass_inspection")
def on_pass(event, obj, user, **kw):
    notify(
        _supplier_users(obj, user),
        "po.inspection_passed",
        f"{obj.number} 验货通过，请准备出货",
        "请上传装箱单等出货资料。",
        obj.get_portal_url(),
    )


@events.subscribe("purchasing.po.fail_inspection")
def on_fail(event, obj, user, **kw):
    notify(
        _supplier_users(obj, user),
        "po.inspection_failed",
        f"{obj.number} 验货不合格，已退回生产",
        f"原因：{_reason(kw)}",
        obj.get_portal_url(),
    )


@events.subscribe("purchasing.po.ship")
def on_ship(event, obj, user, **kw):
    notify(_supplier_users(obj, user), "po.shipped", f"{obj.number} 已确认出货", "", obj.get_portal_url())


@events.subscribe("purchasing.po.cancel")
def on_cancel(event, obj, user, **kw):
    if kw.get("source") != "draft":
        notify(
            _supplier_users(obj, user),
            "po.cancelled",
            f"采购单 {obj.number} 已取消",
            f"原因：{_reason(kw)}",
            obj.get_portal_url(),
        )


@events.subscribe("purchasing.po.date_changed")
def on_date_changed(event, obj, user, old_date=None, new_date=None, reason="", **kw):
    old = f"{old_date:%m-%d}" if old_date else "未定"
    recipients = _owner(obj, user) if user.is_supplier else _supplier_users(obj, user)
    url = obj.get_absolute_url() if user.is_supplier else obj.get_portal_url()
    notify(
        recipients,
        "po.date_changed",
        f"{obj.number} 交期变更：{old} → {new_date:%m-%d}",
        f"原因：{reason}",
        url,
    )


@events.subscribe("purchasing.po.*")
def refresh_alerts(event, **kw):
    scan_alerts.delay()
