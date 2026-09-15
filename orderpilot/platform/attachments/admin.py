from django.contrib import admin

from .models import Attachment


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("uploaded_at", "original_name", "kind", "content_type", "object_id", "uploaded_by")
    list_filter = ("kind",)
    search_fields = ("original_name",)
