"""供应商门户。所有查询都经过 for_user() 做行级隔离：访问别家供应商的单据一律 404。"""

from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from orderpilot.platform.accounts.decorators import supplier_required
from orderpilot.trade.purchasing import ui
from orderpilot.trade.purchasing.models import POStatus, PurchaseOrder

SECTIONS = [
    (
        POStatus.PENDING_CONFIRM,
        "待确认交期",
        "请确认交期；如无法按要求交货，请选择「拒绝 / 要求改单」并说明原因。",
    ),
    (POStatus.IN_PRODUCTION, "生产中", "请及时更新生产节点；交期有变化时请提前修改交期并说明原因。"),
    (POStatus.PENDING_INSPECTION, "待验货", "已申请验货，等待客户安排。"),
    (POStatus.READY_TO_SHIP, "待出货", "验货已通过，请上传装箱单等出货资料。"),
]


def _portal_qs(request):
    return (
        PurchaseOrder.objects.for_user(request.user)
        .visible_to_supplier()
        .select_related("supplier", "customer")
        .with_summary()
    )


@supplier_required
def home(request):
    pos = list(_portal_qs(request).order_by("expected", "pk"))
    sections = [
        {"status": s, "label": label, "hint": hint, "pos": [p for p in pos if p.status == s]}
        for s, label, hint in SECTIONS
    ]
    shipped = sorted(
        (p for p in pos if p.status == POStatus.SHIPPED),
        key=lambda p: p.shipped_at or p.updated_at,
        reverse=True,
    )[:10]
    ctx = {"sections": sections, "shipped": shipped, "supplier": request.user.supplier}
    return render(request, "portal/home.html", ctx)


@supplier_required
def po_detail(request, pk):
    po = get_object_or_404(_portal_qs(request), pk=pk)
    return render(request, "portal/po_detail.html", ui.po_context(po, request.user, "portal"))


@supplier_required
@require_POST
def po_transition(request, pk, name):
    po = get_object_or_404(_portal_qs(request), pk=pk)
    ui.handle_transition(request, po, name)
    return redirect("portal:po_detail", pk=pk)


@supplier_required
@require_POST
def po_change_date(request, pk):
    po = get_object_or_404(_portal_qs(request), pk=pk)
    ui.handle_date_change(request, po)
    return redirect("portal:po_detail", pk=pk)


@supplier_required
@require_POST
def po_milestone(request, pk, mid):
    po = get_object_or_404(_portal_qs(request), pk=pk)
    ui.handle_milestone(request, po, mid)
    return redirect("portal:po_detail", pk=pk)


@supplier_required
@require_POST
def po_upload(request, pk):
    po = get_object_or_404(_portal_qs(request), pk=pk)
    ui.handle_upload(request, po)
    return redirect("portal:po_detail", pk=pk)
