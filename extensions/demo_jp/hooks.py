"""客户特有规则：通过核心提供的 guard 扩展点注册，不修改核心状态机。"""

from orderpilot.platform.attachments.models import Attachment
from orderpilot.platform.attachments.services import attachments_for
from orderpilot.platform.workflow.engine import TransitionError, guard


@guard("purchasing.po", "ship")
def require_packing_list(po, *, user, **payload):
    if not attachments_for(po).filter(kind=Attachment.Kind.PACKING_LIST).exists():
        raise TransitionError("本客户要求：出货前必须上传装箱单")
