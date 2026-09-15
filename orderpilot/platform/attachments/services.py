from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

from orderpilot.platform.audit.services import log_activity


def validate_upload(uploaded):
    ext = uploaded.name.rsplit(".", 1)[-1].lower() if "." in uploaded.name else ""
    if ext not in settings.ORDERPILOT_ATTACHMENT_EXTENSIONS:
        allowed = "、".join(settings.ORDERPILOT_ATTACHMENT_EXTENSIONS)
        raise ValidationError(f"不支持的文件类型 .{ext}，允许：{allowed}")
    max_mb = settings.ORDERPILOT_ATTACHMENT_MAX_MB
    if uploaded.size > max_mb * 1024 * 1024:
        raise ValidationError(f"文件不能超过 {max_mb} MB")


def attachments_for(obj):
    from .models import Attachment

    return Attachment.objects.filter(
        content_type=ContentType.objects.get_for_model(obj), object_id=obj.pk
    ).select_related("uploaded_by")


def add_attachment(obj, uploaded, kind, user, note=""):
    from .models import Attachment

    validate_upload(uploaded)
    att = Attachment.objects.create(
        content_type=ContentType.objects.get_for_model(obj),
        object_id=obj.pk,
        kind=kind,
        file=uploaded,
        original_name=uploaded.name[:255],
        note=note,
        uploaded_by=user,
    )
    log_activity(
        obj, "attachments.uploaded", f"上传{att.get_kind_display()}：{att.original_name}", actor=user
    )
    return att
