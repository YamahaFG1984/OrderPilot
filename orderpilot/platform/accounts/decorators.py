from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def internal_required(view):
    """仅内部员工可访问；供应商账号被引导回门户。"""

    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_internal:
            if request.user.is_supplier:
                return redirect("portal:home")
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


def supplier_required(view):
    """仅供应商账号可访问；内部员工被引导回工作台。"""

    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not (user.is_supplier and user.supplier_id):
            if user.is_internal:
                return redirect("workbench:dashboard")
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper
