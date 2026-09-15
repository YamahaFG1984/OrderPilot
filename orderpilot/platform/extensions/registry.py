"""扩展点注册表。

核心在这里声明扩展点，领域模块和客户扩展通过 ``@registry.register(key)`` 提供实现；
客户扩展需要替换核心实现时，显式传入 ``override=True``。
"""

from django.core.exceptions import ImproperlyConfigured


class Registry:
    def __init__(self, name):
        self.name = name
        self._items = {}

    def register(self, key, *, override=False):
        def deco(obj):
            if key in self._items and not override:
                raise ImproperlyConfigured(f"{self.name}: '{key}' 已注册，如需覆盖请传 override=True")
            self._items[key] = obj
            return obj

        return deco

    def get(self, key):
        try:
            return self._items[key]
        except KeyError:
            raise ImproperlyConfigured(f"{self.name}: 没有注册 '{key}'") from None

    def __contains__(self, key):
        return key in self._items

    def items(self):
        return list(self._items.items())


alert_evaluators = Registry("alert_evaluators")
notification_channels = Registry("notification_channels")
sync_handlers = Registry("sync_handlers")
