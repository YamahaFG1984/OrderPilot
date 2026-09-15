"""采购单详情页的共用逻辑：工作台和供应商门户共用同一套数据和操作处理，只是 URL 命名空间不同。"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from orderpilot.platform.attachments.forms import AttachmentForm
from orderpilot.platform.attachments.services import add_attachment, attachments_for
from orderpilot.platform.audit.services import activities_for
from orderpilot.platform.integrations.services import ref_for
from orderpilot.platform.workflow.engine import TransitionError

from . import services
from .forms import TRANSITION_FORMS, DateChangeForm, MilestoneForm
from .models import REPLY_STATUSES, POStatus
from .workflow import po_workflow


def form_errors(form):
    parts = []
    for field, errors in form.errors.items():
        label = form.fields[field].label if field in form.fields else ""
        parts.append(f"{label}：{'，'.join(errors)}" if label else "，".join(errors))
    return "；".join(parts)


def build_actions(po, user, ns):
    actions = []
    for t in po_workflow.available(po, user):
        form = None
        form_cls = TRANSITION_FORMS.get(t.name)
        if form_cls:
            initial = {}
            if t.name == "confirm":
                initial["promised_date"] = po.required_date
            elif t.name == "ship":
                initial["ship_date"] = timezone.localdate()
            form = form_cls(initial=initial, auto_id=f"id_{t.name}_%s")
        actions.append({"t": t, "form": form, "url": reverse(f"{ns}:po_transition", args=[po.pk, t.name])})
    return actions


def po_context(po, user, ns):
    lines = list(po.lines.select_related("product"))
    can_reply = po.status in REPLY_STATUSES and user.has_perm("purchasing.reply_po", po)
    return {
        "po": po,
        "ns": ns,
        "lines": lines,
        "total_qty": sum(line.quantity for line in lines),
        "total_amount": sum((line.amount or 0) for line in lines),
        "milestones": po.milestones.all(),
        "date_changes": po.date_changes.select_related("changed_by"),
        "shipments": po.shipments.all(),
        "attachments": attachments_for(po),
        "activities": activities_for(po)[:50],
        "actions": build_actions(po, user, ns),
        "can_reply": can_reply,
        "can_upload": po.status != POStatus.CANCELLED,
        "date_form": DateChangeForm(initial={"new_date": po.promised_date}, auto_id="id_date_%s")
        if can_reply
        else None,
        "attachment_form": AttachmentForm(auto_id="id_att_%s"),
        "erp_ref": ref_for(po),
    }


def handle_transition(request, po, name):
    try:
        t = po_workflow.get(name)
        payload = {}
        form_cls = TRANSITION_FORMS.get(name)
        if form_cls:
            form = form_cls(request.POST)
            if not form.is_valid():
                messages.error(request, form_errors(form))
                return
            payload = form.cleaned_data
        po_workflow.run(po, name, user=request.user, **payload)
    except TransitionError as e:
        messages.error(request, str(e))
    except PermissionDenied:
        messages.error(request, "没有权限执行该操作")
    else:
        messages.success(request, f"已完成：{t.label}")


def handle_date_change(request, po):
    form = DateChangeForm(request.POST)
    if not form.is_valid():
        messages.error(request, form_errors(form))
        return
    try:
        services.change_promised_date(
            po, request.user, form.cleaned_data["new_date"], form.cleaned_data["reason"]
        )
    except (TransitionError, PermissionDenied) as e:
        messages.error(request, str(e) or "没有权限执行该操作")
    else:
        messages.success(request, "交期已更新")


def handle_milestone(request, po, milestone_id):
    form = MilestoneForm(request.POST)
    if not form.is_valid():
        messages.error(request, form_errors(form))
        return
    try:
        services.update_milestone(po, milestone_id, request.user, **form.cleaned_data)
    except (TransitionError, PermissionDenied) as e:
        messages.error(request, str(e) or "没有权限执行该操作")
    except po.milestones.model.DoesNotExist:
        messages.error(request, "生产节点不存在")
    else:
        messages.success(request, "生产节点已更新")


def handle_upload(request, po):
    if po.status == POStatus.CANCELLED:
        messages.error(request, "已取消的采购单不能上传附件")
        return
    form = AttachmentForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, form_errors(form))
        return
    try:
        add_attachment(
            po, form.cleaned_data["file"], form.cleaned_data["kind"], request.user, form.cleaned_data["note"]
        )
    except ValidationError as e:
        messages.error(request, "；".join(e.messages))
    else:
        messages.success(request, "附件已上传")
