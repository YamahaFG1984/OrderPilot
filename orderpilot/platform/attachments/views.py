from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404

from .models import Attachment


@login_required
def download(request, pk):
    """附件下载一律经过权限校验：由所属单据声明 ``attachment_view_perm``。"""
    att = get_object_or_404(Attachment, pk=pk)
    obj = att.content_object
    if obj is None:
        raise Http404
    perm = getattr(obj, "attachment_view_perm", None)
    allowed = request.user.has_perm(perm, obj) if perm else request.user.is_internal
    if not allowed:
        raise Http404
    return FileResponse(att.file.open("rb"), as_attachment=True, filename=att.original_name)
