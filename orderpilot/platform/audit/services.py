from django.contrib.contenttypes.models import ContentType


def log_activity(obj, verb, message, *, actor=None, **data):
    from .models import ActivityLog

    return ActivityLog.objects.create(
        content_type=ContentType.objects.get_for_model(obj),
        object_id=obj.pk,
        actor=actor if actor is not None and actor.is_authenticated else None,
        verb=verb,
        message=message,
        data=data,
    )


def activities_for(obj):
    from .models import ActivityLog

    return ActivityLog.objects.filter(
        content_type=ContentType.objects.get_for_model(obj), object_id=obj.pk
    ).select_related("actor")
