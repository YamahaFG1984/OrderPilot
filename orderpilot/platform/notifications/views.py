from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import Notification


@login_required
def notification_list(request):
    items = Notification.objects.filter(recipient=request.user)[:100]
    return render(request, "notifications/list.html", {"notifications": items})


@login_required
def notification_open(request, pk):
    n = get_object_or_404(Notification, pk=pk, recipient=request.user)
    if n.read_at is None:
        n.read_at = timezone.now()
        n.save(update_fields=["read_at"])
    if n.url and url_has_allowed_host_and_scheme(n.url, allowed_hosts={request.get_host()}):
        return redirect(n.url)
    return redirect("notifications:list")


@login_required
@require_POST
def mark_all_read(request):
    Notification.objects.filter(recipient=request.user, read_at__isnull=True).update(read_at=timezone.now())
    return redirect("notifications:list")


@login_required
def bell(request):
    count = Notification.objects.filter(recipient=request.user, read_at__isnull=True).count()
    return render(request, "notifications/_bell.html", {"count": count})
