from .base import *

if ORDERPILOT_EXTENSION is None:
    ORDERPILOT_EXTENSION = "extensions.demo_jp"
    INSTALLED_APPS.insert(0, ORDERPILOT_EXTENSION)

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
MEDIA_ROOT = BASE_DIR / "media-test"

# 测试中任务同步执行，不需要 Redis
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
