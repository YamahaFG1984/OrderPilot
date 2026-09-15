import rules

from orderpilot.platform.accounts.rules import is_internal, is_object_supplier

# 查看采购单：内部员工，或该单所属供应商
rules.add_perm("purchasing.view_po", is_internal | is_object_supplier)
# 管理采购单（新建、提交、验货、出货、取消）：仅内部员工
rules.add_perm("purchasing.manage_po", is_internal)
# 回复采购单（确认交期、改期、更新生产节点）：所属供应商；跟单员也可以代为录入
rules.add_perm("purchasing.reply_po", is_internal | is_object_supplier)
