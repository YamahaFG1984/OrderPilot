"""预警扫描：逐条执行启用的规则，新增、刷新或自动解除预警，并通知相关人员。"""

import logging

from django.contrib.contenttypes.models import ContentType
from django.db import connection, transaction
from django.utils import timezone

from orderpilot.platform.extensions.registry import alert_evaluators
from orderpilot.platform.notifications.services import notify

from .models import Alert, AlertRule

logger = logging.getLogger(__name__)

_SCAN_LOCK_ID = 7_301_001  # PostgreSQL advisory lock，防止定时扫描和事件触发的扫描并发执行


def ensure_rules():
    """代码里注册了、数据库里还没有的规则，按默认值补齐。"""
    for code, evaluator in alert_evaluators.items():
        AlertRule.objects.get_or_create(
            code=code,
            defaults={
                "name": evaluator.default_name or code,
                "description": evaluator.description,
                "severity": evaluator.default_severity,
                "params": dict(evaluator.default_params),
            },
        )


def _try_lock():
    if connection.vendor != "postgresql":
        return True
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_xact_lock(%s)", [_SCAN_LOCK_ID])
        return cursor.fetchone()[0]


def scan():
    ensure_rules()
    now = timezone.now()
    stats = {"opened": 0, "updated": 0, "resolved": 0, "skipped": False}
    to_notify = []
    with transaction.atomic():
        if not _try_lock():
            stats["skipped"] = True
            return stats
        for rule in AlertRule.objects.all():
            active = Alert.objects.filter(rule=rule).exclude(status=Alert.Status.RESOLVED)
            if not rule.enabled or rule.code not in alert_evaluators:
                stats["resolved"] += active.update(status=Alert.Status.RESOLVED, resolved_at=now)
                continue

            evaluator = alert_evaluators.get(rule.code)()
            params = {**evaluator.default_params, **(rule.params or {})}
            seen = set()
            for c in evaluator.evaluate(params):
                ct = ContentType.objects.get_for_model(c.obj)
                key = f"{rule.code}:{ct.pk}:{c.obj.pk}" + (f":{c.key}" if c.key else "")
                seen.add(key)
                alert = active.filter(dedup_key=key).first()
                if alert:
                    alert.title, alert.message, alert.url = c.title, c.message, c.url
                    alert.severity = rule.severity
                    alert.last_seen_at = now
                    alert.save(update_fields=["title", "message", "url", "severity", "last_seen_at"])
                    stats["updated"] += 1
                else:
                    alert = Alert.objects.create(
                        rule=rule,
                        dedup_key=key,
                        content_type=ct,
                        object_id=c.obj.pk,
                        severity=rule.severity,
                        title=c.title,
                        message=c.message,
                        url=c.url,
                    )
                    stats["opened"] += 1
                    to_notify.append((alert, c.recipients))
            # 条件已经不成立的预警自动解除
            stats["resolved"] += active.exclude(dedup_key__in=seen).update(
                status=Alert.Status.RESOLVED, resolved_at=now
            )

        for alert, recipients in to_notify:
            notify(
                recipients,
                "alert.opened",
                f"【{alert.get_severity_display()}】{alert.title}",
                alert.message,
                alert.url,
            )
    logger.info("预警扫描完成：%s", stats)
    return stats


def acknowledge(alert, user):
    alert.status = Alert.Status.ACKNOWLEDGED
    alert.acknowledged_by = user
    alert.acknowledged_at = timezone.now()
    alert.save(update_fields=["status", "acknowledged_by", "acknowledged_at"])
    return alert
