"""OrderPilot 基础配置。环境相关的值一律通过环境变量注入。"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
if (BASE_DIR / ".env").exists():
    environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-insecure-change-me")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_htmx",
    "simple_history",
    "rules.apps.AutodiscoverRulesConfig",
    "django_celery_beat",
    # 平台基础
    "orderpilot.platform.accounts",
    "orderpilot.platform.audit",
    "orderpilot.platform.notifications",
    "orderpilot.platform.attachments",
    "orderpilot.platform.integrations",
    "orderpilot.platform.alerts",
    # 跟单领域
    "orderpilot.trade.masterdata",
    "orderpilot.trade.purchasing",
    "orderpilot.trade.shipping",
    # 界面
    "orderpilot.workbench",
    "orderpilot.portal",
]

# 客户扩展：排在最前面，以便覆盖核心模板
ORDERPILOT_EXTENSION = env("ORDERPILOT_EXTENSION", default="") or None
if ORDERPILOT_EXTENSION:
    INSTALLED_APPS.insert(0, ORDERPILOT_EXTENSION)

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "orderpilot" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "orderpilot.platform.notifications.context_processors.notifications",
            ],
        },
    },
]

DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://orderpilot:orderpilot@localhost:5436/orderpilot"),
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "rules.permissions.ObjectPermissionBackend",
    "django.contrib.auth.backends.ModelBackend",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"

LANGUAGE_CODE = "zh-hans"
LANGUAGES = [("zh-hans", "简体中文"), ("ja", "日本語")]
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "orderpilot" / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = "OrderPilot <noreply@orderpilot.local>"

# ---- Celery ----
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6381/0")
CELERY_TASK_IGNORE_RESULT = True  # 关键结果写数据库，不依赖 Redis
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_ROUTES = {
    "orderpilot.platform.integrations.tasks.*": {"queue": "sync"},
    "orderpilot.platform.notifications.tasks.*": {"queue": "notify"},
}
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_BEAT_SCHEDULE = {
    "scan-alerts": {
        "task": "orderpilot.platform.alerts.tasks.scan_alerts",
        "schedule": env.int("ALERT_SCAN_SECONDS", default=300),
    },
}

# ---- OrderPilot ----
ORDERPILOT_COMPANY_NAME = env("ORDERPILOT_COMPANY_NAME", default="OrderPilot 演示公司")
ORDERPILOT_SUPPLIER_MODEL = "masterdata.Supplier"
ORDERPILOT_ERP_ADAPTER = env(
    "ORDERPILOT_ERP_ADAPTER",
    default="orderpilot.platform.integrations.adapters.mock_kingdee.MockKingdeeAdapter",
)
ORDERPILOT_NOTIFICATION_CHANNELS = ["inapp", "email"]
# 邮件等站外渠道里拼接完整链接用
ORDERPILOT_SITE_URL = env("ORDERPILOT_SITE_URL", default="http://localhost:8010")
# 登录页是否列出演示账号（仅本地演示时开启，公网访问务必关闭）
ORDERPILOT_SHOW_DEMO_ACCOUNTS = env.bool("ORDERPILOT_SHOW_DEMO_ACCOUNTS", default=False)
ORDERPILOT_ATTACHMENT_MAX_MB = 20
ORDERPILOT_ATTACHMENT_EXTENSIONS = ["pdf", "xlsx", "xls", "csv", "docx", "jpg", "jpeg", "png", "zip", "txt"]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"orderpilot": {"handlers": ["console"], "level": "INFO"}},
}

# ---- 安全 ----
# 静态文件由 WhiteNoise 提供：关闭调试模式后 CSS 照常加载，不依赖 runserver --insecure
MIDDLEWARE.insert(
    MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1,
    "whitenoise.middleware.WhiteNoiseMiddleware",
)
WHITENOISE_USE_FINDERS = True  # 直接读取各 app 的 static 目录，无需先 collectstatic

# 登录失败锁定（django-axes）：同一用户名 + IP 连续失败 N 次后锁定一段时间
INSTALLED_APPS.append("axes")
MIDDLEWARE.append("axes.middleware.AxesMiddleware")
AUTHENTICATION_BACKENDS.insert(0, "axes.backends.AxesStandaloneBackend")
AXES_FAILURE_LIMIT = env.int("AXES_FAILURE_LIMIT", default=5)
AXES_COOLOFF_TIME = env.int("AXES_COOLOFF_HOURS", default=1)  # 小时
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = "registration/locked.html"

# 浏览器安全头与 Cookie
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
CSRF_COOKIE_HTTPONLY = True  # htmx 从页面读取 CSRF token，不需要读 Cookie

# 配好域名和 HTTPS 之后设置 DJANGO_HTTPS=true
if env.bool("DJANGO_HTTPS", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
