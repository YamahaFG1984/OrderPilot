from django.db import transaction


def notify(recipients, kind, title, body="", url=""):
    """给一组用户发通知：先写站内信，事务提交后异步投递到其他渠道。"""
    from .models import Notification
    from .tasks import deliver_notification

    seen = set()
    created = []
    for user in recipients:
        if user is None or not user.is_active or user.pk in seen:
            continue
        seen.add(user.pk)
        n = Notification.objects.create(recipient=user, kind=kind, title=title[:200], body=body, url=url)
        created.append(n)
        transaction.on_commit(lambda pk=n.pk: deliver_notification.delay(pk), robust=True)
    return created
