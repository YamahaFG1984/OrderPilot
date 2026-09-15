from celery import shared_task


@shared_task
def run_sync_job_task(job_id):
    from .models import SyncJob
    from .services import run_sync_job

    job = SyncJob.objects.filter(pk=job_id).first()
    if job is not None and job.status == SyncJob.Status.PENDING:
        run_sync_job(job)
