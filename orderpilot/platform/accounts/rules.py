"""通用权限谓词（django-rules）。各领域模块在自己的 rules.py 里用它们组合出具体权限。"""

import rules


@rules.predicate
def is_internal(user):
    return bool(user.is_authenticated and user.is_active and getattr(user, "is_internal", False))


@rules.predicate
def is_supplier(user):
    return bool(user.is_authenticated and user.is_active and getattr(user, "is_supplier", False))


@rules.predicate
def is_object_supplier(user, obj):
    """供应商账号，且对象归属于该供应商。"""
    if obj is None or not is_supplier(user) or not user.supplier_id:
        return False
    return getattr(obj, "supplier_id", None) == user.supplier_id
