from django.apps import AppConfig


class DemoJpConfig(AppConfig):
    """演示用客户扩展（对日业务）：展示如何在不改核心代码的前提下加入客户特有规则。"""

    name = "extensions.demo_jp"
    label = "demo_jp"
    verbose_name = "演示客户扩展（对日）"

    def ready(self):
        from . import hooks  # noqa: F401
