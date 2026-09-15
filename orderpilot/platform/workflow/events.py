"""领域事件：事务提交后再分发，避免事务回滚了副作用却已经执行。

订阅方式::

    @events.subscribe("purchasing.po.submit")      # 精确匹配
    @events.subscribe("purchasing.po.*")           # 前缀匹配
    def handler(event, obj, user, **kwargs): ...
"""

import logging
import threading
from collections import defaultdict
from contextlib import contextmanager
from functools import partial

from django.db import transaction

logger = logging.getLogger(__name__)

_subscribers = defaultdict(list)
_state = threading.local()


def subscribe(pattern):
    def deco(fn):
        _subscribers[pattern].append(fn)
        return fn

    return deco


def _matches(pattern, event):
    if pattern.endswith(".*"):
        return event.startswith(pattern[:-1])
    return pattern == event


def publish(event, **kwargs):
    if getattr(_state, "suppressed", False):
        return
    for pattern, handlers in list(_subscribers.items()):
        if not _matches(pattern, event):
            continue
        for fn in handlers:
            transaction.on_commit(partial(fn, event=event, **kwargs), robust=True)


@contextmanager
def suppressed():
    """临时屏蔽事件分发（用于导入演示数据、批量修复等场景）。"""
    previous = getattr(_state, "suppressed", False)
    _state.suppressed = True
    try:
        yield
    finally:
        _state.suppressed = previous
