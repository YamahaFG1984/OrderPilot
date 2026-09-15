from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    class UserType(models.TextChoices):
        INTERNAL = "internal", _("内部员工")
        SUPPLIER = "supplier", _("供应商")

    user_type = models.CharField(
        _("用户类型"), max_length=16, choices=UserType.choices, default=UserType.INTERNAL
    )
    display_name = models.CharField(_("显示名"), max_length=64, blank=True)
    # 平台层不直接 import 领域模型，供应商模型由配置指定
    supplier = models.ForeignKey(
        settings.ORDERPILOT_SUPPLIER_MODEL,
        verbose_name=_("所属供应商"),
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="users",
    )

    class Meta:
        verbose_name = _("用户")
        verbose_name_plural = _("用户")

    def __str__(self):
        return self.display_name or self.get_full_name() or self.username

    @property
    def is_internal(self):
        return self.user_type == self.UserType.INTERNAL

    @property
    def is_supplier(self):
        return self.user_type == self.UserType.SUPPLIER

    def clean(self):
        super().clean()
        if self.is_supplier and not self.supplier_id:
            raise ValidationError({"supplier": _("供应商账号必须关联供应商")})
        if self.is_internal and self.supplier_id:
            raise ValidationError({"supplier": _("内部员工不能关联供应商")})
