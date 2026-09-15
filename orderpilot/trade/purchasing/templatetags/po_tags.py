from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def status_badge(po):
    return format_html('<span class="badge st-{}">{}</span>', po.status, po.get_status_display())


@register.simple_tag
def due_badge(po):
    if not po.is_active:
        return ""
    days = po.days_left
    if days is None:
        return ""
    if days < 0:
        return format_html('<span class="badge due-overdue">逾期 {} 天</span>', -days)
    if days == 0:
        return mark_safe('<span class="badge due-soon">今天到期</span>')
    if days <= 3:
        return format_html('<span class="badge due-soon">{} 天后到期</span>', days)
    return format_html('<span class="badge due-ok">{} 天后</span>', days)


@register.simple_tag
def severity_badge(alert):
    return format_html('<span class="badge sev-{}">{}</span>', alert.severity, alert.get_severity_display())


@register.filter
def get_item(mapping, key):
    return mapping.get(key)
