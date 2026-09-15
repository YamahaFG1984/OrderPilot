from django.contrib import admin

from .models import Alert, AlertRule


@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "severity", "enabled", "params")
    list_editable = ("severity", "enabled")
    readonly_fields = ("code",)


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ("first_seen_at", "severity", "title", "status", "rule")
    list_filter = ("status", "severity", "rule")
    search_fields = ("title", "message")
