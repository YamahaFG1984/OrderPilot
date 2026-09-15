import logging

from celery import shared_task
from django.conf import settings

from orderpilot.platform.extensions.registry import notification_channels

logger = logging.getLogger(__name__)


@shared_task(autoretry_for=(ConnectionError,), retry_backoff=True, max_retries=3)
def deliver_notification(notification_id):
    from .models import Notification

    n = Notification.objects.select_related("recipient").filter(pk=notification_id).first()
    if n is None:
        return
    for code in settings.ORDERPILOT_NOTIFICATION_CHANNELS:
        if code == "inapp":
            continue
        channel = notification_channels.get(code)()
        try:
            channel.send(n)
        except Exception:
            logger.exception("通知渠道 %s 投递失败：notification=%s", code, n.pk)
