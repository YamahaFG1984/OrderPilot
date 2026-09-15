from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect


class OrderPilotLoginView(LoginView):
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # 请求时读取配置：公网访问时关闭，登录页不列出演示账号
        ctx["show_demo_accounts"] = settings.ORDERPILOT_SHOW_DEMO_ACCOUNTS
        return ctx


@login_required
def home(request):
    if request.user.is_supplier:
        return redirect("portal:home")
    return redirect("workbench:dashboard")
