from django.contrib import admin

from .models import ExternalRef, SyncJob


@admin.register(SyncJob)
class SyncJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "created_at",
        "system",
        "direction",
        "entity",
        "status",
        "triggered_by",
        "finished_at",
    )
    list_filter = ("status", "direction", "entity")
    readonly_fields = [f.name for f in SyncJob._meta.fields]


@admin.register(ExternalRef)
class ExternalRefAdmin(admin.ModelAdmin):
    list_display = ("system", "content_type", "object_id", "external_id", "external_number", "synced_at")
    list_filter = ("system", "content_type")
    search_fields = ("external_id", "external_number")
