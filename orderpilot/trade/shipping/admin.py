from django.contrib import admin

from .models import Shipment


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ("po", "ship_date", "forwarder", "tracking_no", "container_no", "eta")
    search_fields = ("po__number", "tracking_no", "container_no")
