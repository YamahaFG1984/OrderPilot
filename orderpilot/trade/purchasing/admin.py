from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import DeliveryDateChange, Milestone, PurchaseOrder, PurchaseOrderLine


class LineInline(admin.TabularInline):
    model = PurchaseOrderLine
    extra = 0


class MilestoneInline(admin.TabularInline):
    model = Milestone
    extra = 0


class DateChangeInline(admin.TabularInline):
    model = DeliveryDateChange
    extra = 0
    readonly_fields = ("old_date", "new_date", "reason", "changed_by", "created_at")


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(SimpleHistoryAdmin):
    list_display = ("number", "supplier", "customer", "owner", "status", "required_date", "promised_date")
    list_filter = ("status", "supplier", "owner")
    search_fields = ("number",)
    readonly_fields = ("number", "submitted_at", "confirmed_at", "shipped_at")
    inlines = [LineInline, MilestoneInline, DateChangeInline]
