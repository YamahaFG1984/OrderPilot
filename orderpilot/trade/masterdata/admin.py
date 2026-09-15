from django.contrib import admin

from .models import Customer, Product, Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "contact_name", "phone", "lead_time_days", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "currency", "is_active")
    search_fields = ("code", "name")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("part_no", "name", "name_ja", "jan_code", "carton_qty", "status", "default_supplier")
    list_filter = ("status", "default_supplier")
    search_fields = ("part_no", "name", "name_ja", "jan_code")
