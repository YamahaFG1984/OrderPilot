import logging
import traceback

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone
from django.utils.module_loading import import_string

from orderpilot.platform.extensions.registry import sync_handlers

from .models import ExternalRef, SyncJob

logger = logging.getLogger(__name__)


def get_adapter():
    return import_string(settings.ORDERPILOT_ERP_ADAPTER)()


# ---- 外部 ID 映射 ----
def link_ref(obj, system, external_id, external_number=""):
    ref, _ = ExternalRef.objects.update_or_create(
        system=system,
        content_type=ContentType.objects.get_for_model(obj),
        object_id=obj.pk,
        defaults={"external_id": str(external_id), "external_number": external_number},
    )
    return ref


def find_by_ref(model, system, external_id):
    ref = ExternalRef.objects.filter(
        system=system, content_type=ContentType.objects.get_for_model(model), external_id=str(external_id)
    ).first()
    if ref is None:
        return None
    return model._default_manager.filter(pk=ref.object_id).first()


def ref_for(obj, system=None):
    qs = ExternalRef.objects.filter(content_type=ContentType.objects.get_for_model(obj), object_id=obj.pk)
    if system:
        qs = qs.filter(system=system)
    return qs.first()


# ---- 同步任务 ----
def start_sync(entity, direction, *, user=None, **params):
    """创建同步任务，事务提交后交给 Celery sync 队列执行。"""
    from .tasks import run_sync_job_task

    job = SyncJob.objects.create(
        system=get_adapter().system, entity=entity, direction=direction, params=params, triggered_by=user
    )
    transaction.on_commit(lambda: run_sync_job_task.delay(job.pk), robust=True)
    return job


def run_sync_job(job):
    job.status = SyncJob.Status.RUNNING
    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at"])
    try:
        handler = sync_handlers.get(f"{job.direction}:{job.entity}")
        with transaction.atomic():
            stats = handler(get_adapter(), job) or {}
        job.status = SyncJob.Status.SUCCESS
        job.stats = stats
    except Exception:
        logger.exception("同步任务失败：%s", job)
        job.status = SyncJob.Status.FAILED
        job.error = traceback.format_exc()[-4000:]
    job.finished_at = timezone.now()
    job.save(update_fields=["status", "stats", "error", "finished_at"])
    return job
