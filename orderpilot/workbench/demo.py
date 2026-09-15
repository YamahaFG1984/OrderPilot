"""演示账号：账号清单、随机密码生成、凭据文件写入。

凭据文件以 600 权限写在项目根目录（已被 .gitignore 忽略），密码不在终端打印。
"""

import os
import secrets
from pathlib import Path

from django.conf import settings
from django.utils import timezone

INTERNAL_USERS = [
    ("admin", "系统管理员", "admin@example.com", True),
    ("zhang", "张伟（跟单）", "zhangwei@example.com", False),
    ("li", "李娜（跟单）", "lina@example.com", False),
]
SUPPLIER_USERS = [
    ("huamei", "王丽（华美家纺）", "VEN0001"),
    ("jiabao", "陈强（嘉宝日用）", "VEN0002"),
    ("yongxing", "刘洋（永兴塑胶）", "VEN0003"),
]
DEMO_USERNAMES = [u[0] for u in INTERNAL_USERS] + [u[0] for u in SUPPLIER_USERS]
SIMPLE_PASSWORD = "demo1234"

# 去掉容易看错的字符（0/O、1/l/I）
_ALPHABET = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_password(length=12):
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def default_credentials_path():
    return Path(settings.BASE_DIR) / ".demo-credentials"


def write_credentials(rows, path=None):
    """rows: [(用户名, 说明, 密码)]。只有服务器上的当前系统用户可读。"""
    path = Path(path) if path else default_credentials_path()
    width = max(len(r[0]) for r in rows)
    lines = [
        f"# OrderPilot 演示账号（生成于 {timezone.localtime():%Y-%m-%d %H:%M}）",
        f"# 登录地址：{settings.ORDERPILOT_SITE_URL.rstrip('/')}/login/",
        "",
        *(f"{username:<{width}}  {password}  {label}" for username, label, password in rows),
    ]
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(path, 0o600)  # 文件已存在时 os.open 不会修改权限
    return path
