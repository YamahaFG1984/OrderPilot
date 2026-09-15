from celery import shared_task


@shared_task
def scan_alerts():
    from .engine import scan

    return scan()
