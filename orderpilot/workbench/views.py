from collections import defaultdict

from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from orderpilot.platform.accounts.decorators import internal_required
from orderpilot.platform.alerts import engine as alert_engine
from orderpilot.platform.alerts.models import Alert, Severity
from orderpilot.platform.audit.services import log_activity
from orderpilot.platform.integrations.models import SyncJob
from orderpilot.platform.integrations.services import start_sync
from orderpilot.trade.masterdata.models import Supplier
from orderpilot.trade.purchasing import ui
from orderpilot.trade.purchasing.forms import LineFormSet, PurchaseOrderForm
from orderpilot.trade.purchasing.models import POStatus, PurchaseOrder, PurchaseOrderLine

BOARD_STATUSES = [
    POStatus.DRAFT,
    POStatus.PENDING_CONFIRM,
    POStatus.IN_PRODUCTION,
    POStatus.PENDING_INSPECTION,
    POStatus.READY_TO_SHIP,
]


def _next_url(request, fallback):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return nxt
    return fallback


def _open_alerts_by_po(ids):
    ct = ContentType.objects.get_for_model(PurchaseOrder)
    grouped = defaultdict(list)
    qs = Alert.objects.filter(content_type=ct, object_id__in=ids).exclude(status=Alert.Status.RESOLVED)
    for alert in qs:
        grouped[alert.object_id].append(alert)
    return grouped


def _attach_alerts(pos):
    grouped = _open_alerts_by_po([p.pk for p in pos])
    for p in pos:
        p.open_alerts = sorted(grouped.get(p.pk, []), key=lambda a: -a.rank)
        p.top_severity = p.open_alerts[0].severity if p.open_alerts else ""
    return pos


def _scoped(request, default_scope):
    scope = request.GET.get("scope", default_scope)
    qs = (
        PurchaseOrder.objects.for_user(request.user)
        .select_related("supplier", "customer", "owner")
        .with_summary()
    )
    if scope == "mine":
        qs = qs.filter(owner=request.user)
    return qs, scope


def _po_or_404(request, pk):
    return get_object_or_404(
        PurchaseOrder.objects.for_user(request.user).select_related("supplier", "customer", "owner"), pk=pk
    )


# ---------------- 看板 ----------------
@internal_required
def dashboard(request):
    qs, scope = _scoped(request, "mine")
    pos = _attach_alerts(list(qs.filter(status__in=BOARD_STATUSES).order_by("expected", "pk")))
    columns = [
        {"status": s, "label": POStatus(s).label, "pos": [p for p in pos if p.status == s]}
        for s in BOARD_STATUSES
    ]
    active = [p for p in pos if p.is_active]
    kpis = [
        {"label": "跟进中", "value": len(active), "tone": "", "hint": "待确认 ~ 待出货"},
        {
            "label": "待供应商确认",
            "value": sum(p.status == POStatus.PENDING_CONFIRM for p in pos),
            "tone": "",
            "hint": "",
        },
        {
            "label": "7 天内到期",
            "value": sum(p.days_left is not None and 0 <= p.days_left <= 7 for p in active),
            "tone": "warn",
            "hint": "",
        },
        {"label": "已逾期", "value": sum(p.is_overdue for p in active), "tone": "danger", "hint": ""},
        {
            "label": "未处理预警",
            "value": sum(len(p.open_alerts) for p in pos),
            "tone": "danger" if any(p.top_severity == Severity.CRITICAL for p in pos) else "warn",
            "hint": "",
        },
    ]
    return render(request, "workbench/dashboard.html", {"columns": columns, "kpis": kpis, "scope": scope})


# ---------------- 采购单 ----------------
@internal_required
def po_list(request):
    qs, scope = _scoped(request, "all")
    status = request.GET.get("status", "")
    supplier = request.GET.get("supplier", "")
    q = request.GET.get("q", "").strip()
    if status == "active":
        qs = qs.active()
    elif status:
        qs = qs.filter(status=status)
    if supplier.isdigit():
        qs = qs.filter(supplier_id=int(supplier))
    if q:
        matched_lines = PurchaseOrderLine.objects.filter(
            Q(product__part_no__icontains=q) | Q(product__name__icontains=q) | Q(product__jan_code=q)
        ).values("po_id")
        qs = qs.filter(Q(number__icontains=q) | Q(pk__in=matched_lines))
    page = Paginator(qs.order_by("-created_at", "-pk"), 25).get_page(request.GET.get("page"))
    _attach_alerts(page.object_list)
    ctx = {
        "page": page,
        "scope": scope,
        "status": status,
        "supplier": supplier,
        "q": q,
        "statuses": POStatus.choices,
        "suppliers": Supplier.objects.filter(is_active=True),
    }
    return render(request, "workbench/po_list.html", ctx)


def _po_form(request, po, is_new):
    form = PurchaseOrderForm(request.POST or None, instance=po)
    formset = LineFormSet(request.POST or None, instance=po, prefix="lines")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            po = form.save()
            formset.instance = po
            formset.save()
            log_activity(
                po, "purchasing.po.saved", "创建采购单" if is_new else "修改采购单", actor=request.user
            )
        messages.success(request, f"采购单 {po.number} 已保存")
        return redirect("workbench:po_detail", pk=po.pk)
    return render(
        request, "workbench/po_form.html", {"form": form, "formset": formset, "po": po, "is_new": is_new}
    )


@internal_required
def po_create(request):
    from django.utils import timezone

    po = PurchaseOrder(owner=request.user, order_date=timezone.localdate())
    return _po_form(request, po, is_new=True)


@internal_required
def po_edit(request, pk):
    po = _po_or_404(request, pk)
    if po.status != POStatus.DRAFT:
        messages.error(request, "只有草稿状态的采购单可以修改")
        return redirect("workbench:po_detail", pk=po.pk)
    return _po_form(request, po, is_new=False)


@internal_required
def po_detail(request, pk):
    po = _po_or_404(request, pk)
    ctx = ui.po_context(po, request.user, "workbench")
    ctx["alerts"] = sorted(_open_alerts_by_po([po.pk]).get(po.pk, []), key=lambda a: -a.rank)
    return render(request, "workbench/po_detail.html", ctx)


@internal_required
@require_POST
def po_transition(request, pk, name):
    po = _po_or_404(request, pk)
    ui.handle_transition(request, po, name)
    return redirect("workbench:po_detail", pk=pk)


@internal_required
@require_POST
def po_change_date(request, pk):
    po = _po_or_404(request, pk)
    ui.handle_date_change(request, po)
    return redirect("workbench:po_detail", pk=pk)


@internal_required
@require_POST
def po_milestone(request, pk, mid):
    po = _po_or_404(request, pk)
    ui.handle_milestone(request, po, mid)
    return redirect("workbench:po_detail", pk=pk)


@internal_required
@require_POST
def po_upload(request, pk):
    po = _po_or_404(request, pk)
    ui.handle_upload(request, po)
    return redirect("workbench:po_detail", pk=pk)


# ---------------- 预警 ----------------
@internal_required
def alert_list(request):
    status = request.GET.get("status", "open")
    qs = Alert.objects.select_related("rule", "acknowledged_by")
    if status == "open":
        qs = qs.exclude(status=Alert.Status.RESOLVED)
    elif status == "resolved":
        qs = qs.filter(status=Alert.Status.RESOLVED)
    severity = request.GET.get("severity", "")
    if severity:
        qs = qs.filter(severity=severity)
    alerts = sorted(
        qs[:200], key=lambda a: (a.status != Alert.Status.OPEN, -a.rank, -a.first_seen_at.timestamp())
    )
    counts = {
        s: Alert.objects.exclude(status=Alert.Status.RESOLVED).filter(severity=s).count()
        for s in Severity.values
    }
    ctx = {
        "alerts": alerts,
        "status": status,
        "severity": severity,
        "severities": Severity.choices,
        "counts": counts,
    }
    return render(request, "workbench/alerts.html", ctx)


@internal_required
@require_POST
def alert_ack(request, pk):
    alert = get_object_or_404(Alert, pk=pk)
    alert_engine.acknowledge(alert, request.user)
    messages.success(request, "已标记为知悉")
    return redirect(_next_url(request, "workbench:alerts"))


@internal_required
@require_POST
def alert_scan(request):
    stats = alert_engine.scan()
    if stats.get("skipped"):
        messages.info(request, "另一个扫描正在进行，请稍后再试")
    else:
        messages.success(
            request,
            f"扫描完成：新增 {stats['opened']} 条，刷新 {stats['updated']} 条，解除 {stats['resolved']} 条",
        )
    return redirect(_next_url(request, "workbench:alerts"))


# ---------------- ERP 同步 ----------------
def _sync_ctx():
    jobs = list(SyncJob.objects.select_related("triggered_by")[:20])
    return {"jobs": jobs, "has_active": any(j.is_active for j in jobs)}


@internal_required
def sync_page(request):
    return render(request, "workbench/sync.html", _sync_ctx())


@internal_required
def sync_jobs(request):
    return render(request, "workbench/_sync_jobs.html", _sync_ctx())


@internal_required
@require_POST
def sync_start(request):
    start_sync("masterdata", SyncJob.Direction.PULL, user=request.user)
    messages.success(request, "已创建同步任务，正在后台执行")
    return redirect("workbench:sync")
