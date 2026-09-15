from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from orderpilot.platform.accounts.views import OrderPilotLoginView, home

admin.site.site_header = "OrderPilot 管理后台"
admin.site.site_title = "OrderPilot"

# 注意：MEDIA 不直接对外提供，附件一律经过 attachments:download 做权限校验
urlpatterns = [
    path("", home, name="home"),
    path("login/", OrderPilotLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("admin/", admin.site.urls),
    path("w/", include("orderpilot.workbench.urls")),
    path("portal/", include("orderpilot.portal.urls")),
    path("notifications/", include("orderpilot.platform.notifications.urls")),
    path("attachments/", include("orderpilot.platform.attachments.urls")),
]
