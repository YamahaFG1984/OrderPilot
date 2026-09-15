"""轻量状态机。

- 状态和转换由核心定义（``Workflow`` + ``Transition``）；
- 核心副作用通过 ``@workflow.handler(name)`` 注册；
- 客户扩展只能通过 ``@guard(workflow, name)`` 增加转换前校验，或订阅领域事件做转换后副作用。
"""

import datetime
from collections import defaultdict
from dataclasses import dataclass

from django.core.exceptions import PermissionDenied
from django.db import transaction

from orderpilot.platform.audit.services import log_activity

from . import events


class TransitionError(Exception):
    """业务规则不允许执行该操作。消息会直接展示给用户。"""


@dataclass(frozen=True)
class Transition:
    name: str
    label: str
    source: tuple
    target: str
    permission: str
    style: str = "default"  # 界面按钮样式：primary / danger / default


_guards = defaultdict(list)


def guard(workflow_name, transition_name):
    """注册转换前校验。校验函数签名：``fn(obj, *, user, **payload)``，不通过时抛 TransitionError。"""

    def deco(fn):
        _guards[(workflow_name, transition_name)].append(fn)
        return fn

    return deco


def _loggable(payload):
    simple = (str, int, float, bool, datetime.date)
    return {k: v for k, v in payload.items() if isinstance(v, simple) and v != ""}


class Workflow:
    def __init__(self, name, transitions, state_field="status"):
        self.name = name
        self.state_field = state_field
        self.transitions = {t.name: t for t in transitions}
        self._handlers = {}

    def handler(self, transition_name):
        def deco(fn):
            self._handlers[transition_name] = fn
            return fn

        return deco

    def get(self, name):
        try:
            return self.transitions[name]
        except KeyError:
            raise TransitionError(f"未知操作：{name}") from None

    def available(self, obj, user):
        state = getattr(obj, self.state_field)
        return [
            t for t in self.transitions.values() if state in t.source and user.has_perm(t.permission, obj)
        ]

    def run(self, obj, name, *, user, **payload):
        t = self.get(name)
        with transaction.atomic():
            # 加行锁并以数据库中的状态为准，防止并发重复操作
            locked = type(obj)._default_manager.select_for_update().get(pk=obj.pk)
            state = getattr(locked, self.state_field)
            setattr(obj, self.state_field, state)

            if state not in t.source:
                raise TransitionError(f"当前状态不能执行「{t.label}」")
            if not user.has_perm(t.permission, obj):
                raise PermissionDenied(f"没有权限执行「{t.label}」")
            for check in _guards[(self.name, name)]:
                check(obj, user=user, **payload)

            handler = self._handlers.get(name)
            if handler:
                handler(obj, user=user, **payload)
            setattr(obj, self.state_field, t.target)
            obj.save()

            log_activity(
                obj,
                f"{self.name}.{name}",
                t.label,
                actor=user,
                source=state,
                target=t.target,
                **_loggable(payload),
            )
            events.publish(
                f"{self.name}.{name}", obj=obj, user=user, source=state, target=t.target, payload=payload
            )
        return obj
