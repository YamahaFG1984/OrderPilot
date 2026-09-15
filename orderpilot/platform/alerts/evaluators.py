"""预警规则的实现基类。领域模块用 ``@alert_evaluators.register(code)`` 注册具体规则。"""

from dataclasses import dataclass, field
from typing import Any

from .models import Severity


@dataclass
class AlertCandidate:
    obj: Any
    title: str
    message: str = ""
    url: str = ""
    recipients: list = field(default_factory=list)
    key: str = ""  # 同一对象同一规则下需要区分多条预警时使用（如不同的生产节点）


class Evaluator:
    default_name = ""
    description = ""
    default_severity = Severity.WARNING
    default_params: dict = {}

    def evaluate(self, params):
        """返回 AlertCandidate 的可迭代对象。"""
        raise NotImplementedError
