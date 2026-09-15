"""通知渠道。客户扩展可以注册新渠道（例如企业微信、钉钉 webhook），并在配置中启用。"""

from django.conf import settings
from django.core.mail import send_mail

from orderpilot.platform.extensions.registry import notification_channels


class Channel:
    code = ""

    def send(self, notification):
        raise NotImplementedError


@notification_channels.register("inapp")
class InAppChannel(Channel):
    """Notification 记录本身就是站内信，无需额外投递。"""

    code = "inapp"

    def send(self, notification):
        return None


@notification_channels.register("email")
class EmailChannel(Channel):
    code = "email"

    def send(self, notification):
        email = notification.recipient.email
        if not email:
            return
        body = notification.body
        if notification.url:
            url = notification.url
            if url.startswith("/"):
                url = settings.ORDERPILOT_SITE_URL.rstrip("/") + url
            body = f"{body}\n\n查看详情：{url}".strip()
        send_mail(
            subject=f"[OrderPilot] {notification.title}",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
