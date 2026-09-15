"""给演示账号换成随机密码：旧密码和已登录的会话立即失效，新密码写入凭据文件，不在终端打印。

uv run python manage.py rotate_demo_passwords
cat .demo-credentials
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from orderpilot.workbench.demo import DEMO_USERNAMES, generate_password, write_credentials


class Command(BaseCommand):
    help = "给演示账号换成随机密码，写入 .demo-credentials（权限 600）"

    def add_arguments(self, parser):
        parser.add_argument("--output", help="凭据文件路径，默认为项目根目录的 .demo-credentials")

    def handle(self, *args, output=None, **options):
        users = list(
            get_user_model().objects.filter(username__in=DEMO_USERNAMES).order_by("user_type", "username")
        )
        if not users:
            raise CommandError("没有找到演示账号，请先运行 seed_demo")

        rows = []
        for user in users:
            password = generate_password()
            user.set_password(password)
            user.save(update_fields=["password"])
            rows.append((user.username, str(user), password))
        path = write_credentials(rows, output)

        done = f"已为 {len(rows)} 个演示账号换成随机密码，旧密码和已登录会话立即失效"
        self.stdout.write(self.style.SUCCESS(done))
        self.stdout.write(f"  凭据文件：{path}（仅当前系统用户可读）")
        self.stdout.write(f"  查看：cat {path}")
