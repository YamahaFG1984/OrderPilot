"""行级数据隔离：安全底线。

所有带供应商归属的模型，其 QuerySet 都继承 ``SupplierScopedQuerySet``；
视图里统一通过 ``Model.objects.for_user(request.user)`` 取数，
这样供应商账号永远只能看到自己的数据。
"""

from django.db import models


class SupplierScopedQuerySet(models.QuerySet):
    supplier_field = "supplier"

    def for_user(self, user):
        if not user.is_authenticated or not user.is_active:
            return self.none()
        if user.is_internal:
            return self
        if user.is_supplier and user.supplier_id:
            return self.filter(**{f"{self.supplier_field}_id": user.supplier_id})
        return self.none()
