from .base import *

DEBUG = env.bool("DJANGO_DEBUG", default=True)
WHITENOISE_AUTOREFRESH = DEBUG  # 调试时修改 CSS 无需重启

# 本地演示默认启用对日演示扩展
if ORDERPILOT_EXTENSION is None:
    ORDERPILOT_EXTENSION = "extensions.demo_jp"
    INSTALLED_APPS.insert(0, ORDERPILOT_EXTENSION)

# 演示时预警扫描更频繁
CELERY_BEAT_SCHEDULE["scan-alerts"]["schedule"] = env.int("ALERT_SCAN_SECONDS", default=60)
