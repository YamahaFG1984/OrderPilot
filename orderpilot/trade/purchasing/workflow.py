"""采购单标准状态机（核心定义）。客户扩展只能通过 guard 和领域事件介入，不能改这里。"""

from django.utils import timezone

from orderpilot.platform.workflow.engine import Transition, TransitionError, Workflow
from orderpilot.trade.masterdata.models import Product
from orderpilot.trade.shipping.models import Shipment

from .models import DeliveryDateChange, Milestone, POStatus
from .services import mark_milestone_done, plan_milestones

S = POStatus
MANAGE = "purchasing.manage_po"
REPLY = "purchasing.reply_po"

po_workflow = Workflow(
    "purchasing.po",
    [
        Transition("submit", "提交给供应商", (S.DRAFT,), S.PENDING_CONFIRM, MANAGE, "primary"),
        Transition("confirm", "确认交期", (S.PENDING_CONFIRM,), S.IN_PRODUCTION, REPLY, "primary"),
        Transition("reject", "拒绝 / 要求改单", (S.PENDING_CONFIRM,), S.DRAFT, REPLY, "danger"),
        Transition(
            "finish_production",
            "生产完工，申请验货",
            (S.IN_PRODUCTION,),
            S.PENDING_INSPECTION,
            REPLY,
            "primary",
        ),
        Transition(
            "pass_inspection", "验货通过", (S.PENDING_INSPECTION,), S.READY_TO_SHIP, MANAGE, "primary"
        ),
        Transition(
            "fail_inspection",
            "验货不合格，退回生产",
            (S.PENDING_INSPECTION,),
            S.IN_PRODUCTION,
            MANAGE,
            "danger",
        ),
        Transition("ship", "确认出货", (S.READY_TO_SHIP,), S.SHIPPED, MANAGE, "primary"),
        Transition(
            "cancel",
            "取消采购单",
            (S.DRAFT, S.PENDING_CONFIRM, S.IN_PRODUCTION, S.PENDING_INSPECTION, S.READY_TO_SHIP),
            S.CANCELLED,
            MANAGE,
            "danger",
        ),
    ],
)


def _require(value, message):
    if not value:
        raise TransitionError(message)


@po_workflow.handler("submit")
def _submit(po, *, user, **_):
    lines = list(po.lines.select_related("product"))
    _require(lines, "采购单至少需要一行商品")
    discontinued = [
        line.product.part_no for line in lines if line.product.status == Product.Status.DISCONTINUED
    ]
    if discontinued:
        raise TransitionError(f"以下商品已废番，不能下单：{'、'.join(discontinued)}")
    _require(po.required_date, "请填写要求交期")
    po.submitted_at = timezone.now()
    po.reject_reason = ""


@po_workflow.handler("confirm")
def _confirm(po, *, user, promised_date=None, **_):
    _require(promised_date, "请填写承诺交期")
    if promised_date < timezone.localdate():
        raise TransitionError("承诺交期不能早于今天")
    DeliveryDateChange.objects.create(
        po=po, old_date=po.promised_date, new_date=promised_date, reason="供应商确认交期", changed_by=user
    )
    po.promised_date = promised_date
    po.confirmed_at = timezone.now()
    plan_milestones(po)


@po_workflow.handler("reject")
def _reject(po, *, user, reason="", **_):
    _require(reason, "请填写拒绝或改单的原因")
    po.reject_reason = reason


@po_workflow.handler("finish_production")
def _finish_production(po, *, user, **_):
    mark_milestone_done(po, Milestone.Kind.DONE)


@po_workflow.handler("pass_inspection")
def _pass_inspection(po, *, user, **_):
    mark_milestone_done(po, Milestone.Kind.INSPECTION)


@po_workflow.handler("fail_inspection")
def _fail_inspection(po, *, user, reason="", **_):
    _require(reason, "请填写验货不合格的原因")


@po_workflow.handler("ship")
def _ship(po, *, user, ship_date=None, forwarder="", tracking_no="", container_no="", eta=None, note="", **_):
    _require(ship_date, "请填写出货日期")
    Shipment.objects.create(
        po=po,
        ship_date=ship_date,
        forwarder=forwarder,
        tracking_no=tracking_no,
        container_no=container_no,
        eta=eta,
        note=note,
        created_by=user,
    )
    po.shipped_at = timezone.now()


@po_workflow.handler("cancel")
def _cancel(po, *, user, reason="", **_):
    _require(reason, "请填写取消原因")
