from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User

OP_FIELDS = ("user_type", "display_name", "supplier")


@admin.register(User)
class OrderPilotUserAdmin(UserAdmin):
    list_display = ("username", "display_name", "user_type", "supplier", "email", "is_active", "is_staff")
    list_filter = ("user_type", "is_active", "is_staff")
    search_fields = ("username", "display_name", "email")
    fieldsets = UserAdmin.fieldsets + (("OrderPilot", {"fields": OP_FIELDS}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("OrderPilot", {"fields": OP_FIELDS}),)
