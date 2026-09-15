def notifications(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    from .models import Notification

    return {"unread_notifications": Notification.objects.filter(recipient=user, read_at__isnull=True).count()}
