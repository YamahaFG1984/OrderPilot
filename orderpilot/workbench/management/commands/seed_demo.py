"""导入演示数据：账号、主数据（通过模拟金蝶适配器同步）以及覆盖各种状态和异常的采购单。

uv run python manage.py seed_demo                      # 空库初始化，账号使用随机密码
uv run python manage.py seed_demo --reset              # 清空业务数据后重建
uv run python manage.py seed_demo --simple-passwords   # 本地演示：所有账号密码为 demo1234

随机密码写入项目根目录的 .demo-credentials（权限 600），不在终端打印。
"""

from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from orderpilot.platform.alerts import engine as alert_engine
from orderpilot.platform.alerts.models import Alert
from orderpilot.platform.attachments.models import Attachment
from orderpilot.platform.attachments.services import add_attachment
from orderpilot.platform.audit.models import ActivityLog
from orderpilot.platform.audit.services import activities_for, log_activity
from orderpilot.platform.integrations.models import ExternalRef, SyncJob
from orderpilot.platform.integrations.services import get_adapter, run_sync_job
from orderpilot.platform.notifications.models import Notification
from orderpilot.platform.notifications.services import notify
from orderpilot.platform.workflow import events
from orderpilot.trade.masterdata.models import Customer, Product, Supplier
from orderpilot.trade.purchasing.models import DeliveryDateChange, Milestone, PurchaseOrder, PurchaseOrderLine
from orderpilot.trade.purchasing.services import mark_milestone_done
from orderpilot.trade.purchasing.workflow import po_workflow
from orderpilot.trade.shipping.models import Shipment
from orderpilot.workbench.demo import (
    DEMO_USERNAMES,
    INTERNAL_USERS,
    SIMPLE_PASSWORD,
    SUPPLIER_USERS,
    generate_password,
    write_credentials,
)

PRICES = {
    "HM-TW-3460": "6.80",
    "HM-TW-6012": "18.50",
    "HM-GZ-2525": "3.20",
    "HM-TW-OLD1": "6.20",
    "JB-BT-350": "22.00",
    "JB-BT-500": "26.50",
    "JB-LB-800": "15.80",
    "YX-SB-L": "12.60",
    "YX-SB-M": "8.90",
    "YX-HK-10": "4.50",
}
MS = Milestone.Kind


class Command(BaseCommand):
    help = "导入演示数据（账号、主数据、各种状态的采购单）"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="先清空业务数据和演示账号")
        parser.add_argument(
            "--simple-passwords",
            action="store_true",
            help=f"所有账号使用简单密码 {SIMPLE_PASSWORD}（仅限本地演示，不要用于公网）",
        )

    def handle(self, *args, reset=False, simple_passwords=False, **options):
        if reset:
            self._reset()
        elif PurchaseOrder.objects.exists():
            raise CommandError("数据库里已有采购单。如需重建演示数据，请加 --reset")

        self.today = timezone.localdate()
        self.simple_passwords = simple_passwords
        self.credentials = []
        with events.suppressed(), transaction.atomic():
            self._users_and_masterdata()
            self._purchase_orders()
        stats = alert_engine.scan()
        credentials_path = None if simple_passwords else write_credentials(self.credentials)
        self._summary(stats, credentials_path)

    def _set_password(self, user):
        password = SIMPLE_PASSWORD if self.simple_passwords else generate_password()
        user.set_password(password)
        self.credentials.append((user.username, user.display_name, password))

    # ------------------------------------------------------------------
    def _reset(self):
        User = get_user_model()
        for att in Attachment.objects.all():
            att.file.delete(save=False)
        for model in (Alert, Notification, ActivityLog, Attachment, Shipment, DeliveryDateChange, Milestone):
            model.objects.all().delete()
        PurchaseOrderLine.objects.all().delete()
        PurchaseOrder.history.all().delete()
        PurchaseOrder.objects.all().delete()
        ExternalRef.objects.all().delete()
        SyncJob.objects.all().delete()
        User.objects.filter(username__in=DEMO_USERNAMES).delete()
        Product.objects.all().delete()
        Supplier.objects.all().delete()
        Customer.objects.all().delete()
        self.stdout.write("已清空业务数据")

    def _users_and_masterdata(self):
        User = get_user_model()
        self.users = {}
        for username, name, email, is_admin in INTERNAL_USERS:
            u = User(username=username, display_name=name, email=email, user_type="internal")
            u.is_staff = u.is_superuser = is_admin
            self._set_password(u)
            u.save()
            self.users[username] = u

        job = SyncJob.objects.create(
            system=get_adapter().system,
            entity="masterdata",
            direction="pull",
            triggered_by=self.users["admin"],
        )
        run_sync_job(job)
        if job.status != SyncJob.Status.SUCCESS:
            raise CommandError(f"主数据同步失败：\n{job.error}")

        for username, name, code in SUPPLIER_USERS:
            u = User(
                username=username,
                display_name=name,
                user_type="supplier",
                supplier=Supplier.objects.get(code=code),
                email=f"{username}@example.com",
            )
            self._set_password(u)
            u.save()
            self.users[username] = u

    # ------------------------------------------------------------------
    def _d(self, offset):
        return self.today + timedelta(days=offset)

    def _po(self, supplier, customer, owner, order_offset, required_offset, lines, note=""):
        po = PurchaseOrder.objects.create(
            supplier=Supplier.objects.get(code=supplier),
            customer=Customer.objects.get(code=customer),
            owner=self.users[owner],
            order_date=self._d(order_offset),
            required_date=self._d(required_offset),
            note=note,
        )
        for part_no, cartons in lines:
            product = Product.objects.get(part_no=part_no)
            PurchaseOrderLine.objects.create(
                po=po,
                product=product,
                quantity=cartons * product.carton_qty,
                unit_price=Decimal(PRICES[part_no]),
            )
        log_activity(po, "purchasing.po.saved", "创建采购单", actor=self.users[owner])
        return po

    def _run(self, po, name, username, **payload):
        po_workflow.run(po, name, user=self.users[username], **payload)
        po.refresh_from_db()
        if name == "submit":
            # 导入时事件被屏蔽，这里同步推送一次 ERP，让演示单据带上 ERP 采购订单号
            job = SyncJob.objects.create(
                system=get_adapter().system,
                entity="purchase_order",
                direction="push",
                params={"object_id": po.pk},
                triggered_by=self.users[username],
            )
            run_sync_job(job)

    def _supplier_of(self, po):
        return next(u for u, _, code in SUPPLIER_USERS if code == po.supplier.code)

    def _confirm(self, po, promised_offset):
        self._run(po, "submit", po.owner.username)
        self._run(
            po, "confirm", self._supplier_of(po), promised_date=max(self._d(promised_offset), self.today)
        )

    def _set_promised(self, po, offset):
        """模拟时间流逝：把承诺交期（和首次确认记录）改到过去。"""
        PurchaseOrder.objects.filter(pk=po.pk).update(promised_date=self._d(offset))
        DeliveryDateChange.objects.filter(po=po).update(new_date=self._d(offset))
        po.refresh_from_db()

    def _milestones(self, po, plan):
        for kind, (planned, actual) in plan.items():
            Milestone.objects.filter(po=po, kind=kind).update(
                planned_date=self._d(planned), actual_date=self._d(actual) if actual is not None else None
            )

    def _attach(self, po, kind, filename, username):
        content = ContentFile(f"{filename}\n采购单：{po.number}\n（演示文件）\n".encode(), name=filename)
        add_attachment(po, content, kind, self.users[username])

    def _backdate(self, po, submitted_offset=None, confirmed_offset=None):
        now = timezone.now()
        start = timezone.make_aware(datetime.combine(po.order_date, time(9, 30)))
        updates = {"created_at": start}
        if submitted_offset is not None:
            updates["submitted_at"] = timezone.make_aware(
                datetime.combine(self._d(submitted_offset), time(10, 15))
            )
        if confirmed_offset is not None:
            updates["confirmed_at"] = timezone.make_aware(
                datetime.combine(self._d(confirmed_offset), time(15, 40))
            )
        PurchaseOrder.objects.filter(pk=po.pk).update(**updates)
        # 时间线按顺序均匀分布在下单日到现在之间
        logs = list(activities_for(po).order_by("id"))
        end = max(now - timedelta(hours=2), start + timedelta(minutes=len(logs) + 1))
        step = (end - start) / max(len(logs), 1)
        for i, log in enumerate(logs):
            ActivityLog.objects.filter(pk=log.pk).update(created_at=start + step * i)

    def _purchase_orders(self):
        # A. 草稿：秋季补货
        a = self._po(
            "VEN0001", "CUST001", "zhang", 0, 45, [("HM-TW-3460", 10), ("HM-TW-6012", 8)], "秋季补货第一批"
        )
        self._backdate(a)

        # B. 已提交 4 天，供应商未确认 → 预警
        b = self._po("VEN0002", "CUST001", "zhang", -5, 28, [("JB-BT-350", 20), ("JB-BT-500", 15)])
        self._run(b, "submit", "zhang")
        self._backdate(b, submitted_offset=-4)

        # C. 刚提交，待确认
        c = self._po("VEN0003", "CUST002", "li", -1, 35, [("YX-SB-L", 30), ("YX-SB-M", 20)])
        self._run(c, "submit", "li")
        self._backdate(c, submitted_offset=0)

        # D. 生产中，一切正常
        d = self._po("VEN0001", "CUST002", "zhang", -12, 25, [("HM-GZ-2525", 15)])
        self._confirm(d, 22)
        self._milestones(
            d, {MS.MATERIAL: (-4, -3), MS.START: (2, None), MS.DONE: (20, None), MS.INSPECTION: (22, None)}
        )
        self._backdate(d, submitted_offset=-11, confirmed_offset=-10)

        # E. 生产中，2 天后到期 → 交期临近
        e = self._po("VEN0002", "CUST001", "zhang", -25, 5, [("JB-LB-800", 25)])
        self._confirm(e, 2)
        self._milestones(
            e, {MS.MATERIAL: (-15, -14), MS.START: (-12, -12), MS.DONE: (0, None), MS.INSPECTION: (2, None)}
        )
        self._backdate(e, submitted_offset=-24, confirmed_offset=-23)

        # F. 已逾期 3 天，交期改过一次，完工节点也超期 → 严重预警
        f = self._po(
            "VEN0001",
            "CUST001",
            "zhang",
            -40,
            -1,
            [("HM-TW-3460", 20), ("HM-GZ-2525", 10)],
            "客户门店促销用，交期敏感",
        )
        self._confirm(f, 0)
        self._set_promised(f, -6)
        DeliveryDateChange.objects.create(
            po=f,
            old_date=self._d(-6),
            new_date=self._d(-3),
            reason="原料棉纱到货延迟 3 天",
            changed_by=self.users["huamei"],
        )
        PurchaseOrder.objects.filter(pk=f.pk).update(promised_date=self._d(-3))
        log_activity(
            f, "purchasing.po.date_changed", "交期变更（原料棉纱到货延迟 3 天）", actor=self.users["huamei"]
        )
        self._milestones(
            f, {MS.MATERIAL: (-30, -26), MS.START: (-24, -22), MS.DONE: (-5, None), MS.INSPECTION: (-3, None)}
        )
        self._backdate(f, submitted_offset=-39, confirmed_offset=-37)

        # G. 承诺交期晚于要求交期 9 天
        g = self._po("VEN0003", "CUST002", "li", -8, 21, [("YX-HK-10", 12)])
        self._confirm(g, 30)
        self._backdate(g, submitted_offset=-7, confirmed_offset=-6)

        # H. 备料节点超期 4 天
        h = self._po("VEN0002", "CUST002", "li", -15, 18, [("JB-BT-500", 30)])
        self._confirm(h, 16)
        self._milestones(
            h, {MS.MATERIAL: (-4, None), MS.START: (3, None), MS.DONE: (14, None), MS.INSPECTION: (16, None)}
        )
        self._backdate(h, submitted_offset=-14, confirmed_offset=-13)

        # I. 已完工，待验货
        i = self._po("VEN0003", "CUST001", "zhang", -30, 4, [("YX-SB-M", 40)])
        self._confirm(i, 3)
        self._milestones(
            i, {MS.MATERIAL: (-20, -21), MS.START: (-18, -18), MS.DONE: (0, None), MS.INSPECTION: (3, None)}
        )
        self._run(i, "finish_production", "yongxing")
        self._backdate(i, submitted_offset=-29, confirmed_offset=-28)

        # J. 验货通过、待出货，但还没上传装箱单 → 演示客户扩展的出货校验
        j = self._po("VEN0001", "CUST002", "zhang", -35, 2, [("HM-TW-6012", 12)])
        self._confirm(j, 1)
        self._milestones(
            j, {MS.MATERIAL: (-25, -25), MS.START: (-22, -21), MS.DONE: (-3, -3), MS.INSPECTION: (-1, None)}
        )
        self._run(j, "finish_production", "huamei")
        self._attach(j, Attachment.Kind.INSPECTION, "验货报告.txt", "zhang")
        self._run(j, "pass_inspection", "zhang")
        self._backdate(j, submitted_offset=-34, confirmed_offset=-33)

        # K. 已出货
        k = self._po("VEN0002", "CUST001", "zhang", -45, -5, [("JB-BT-350", 30)])
        self._confirm(k, 0)
        self._set_promised(k, -7)
        self._milestones(
            k, {MS.MATERIAL: (-35, -35), MS.START: (-32, -32), MS.DONE: (-10, -10), MS.INSPECTION: (-8, -8)}
        )
        mark_milestone_done(k, MS.DONE)
        self._run(k, "finish_production", "jiabao")
        self._run(k, "pass_inspection", "zhang")
        self._attach(k, Attachment.Kind.PACKING_LIST, "装箱单.txt", "jiabao")
        self._attach(k, Attachment.Kind.INVOICE, "商业发票.txt", "jiabao")
        self._run(
            k,
            "ship",
            "zhang",
            ship_date=self._d(-6),
            forwarder="东海国际货运（示例）",
            tracking_no="SHTYO2409001",
            container_no="TCLU1234567",
            eta=self._d(-1),
        )
        self._backdate(k, submitted_offset=-44, confirmed_offset=-43)

        # L. 已取消
        l_po = self._po("VEN0003", "CUST002", "li", -10, 30, [("YX-SB-L", 10)])
        self._run(l_po, "submit", "li")
        self._run(l_po, "cancel", "li", reason="客户取消该批次订单")
        self._backdate(l_po, submitted_offset=-9)

        # M. 草稿里含废番商品 → 提交时会被拦截
        m = self._po(
            "VEN0001",
            "CUST001",
            "li",
            0,
            40,
            [("HM-TW-OLD1", 10), ("HM-TW-3460", 5)],
            "含旧款条纹毛巾，待确认是否已废番",
        )
        self._backdate(m)

        # 给供应商补上「新采购单待确认」通知（导入时事件被屏蔽）
        for po in (b, c):
            notify(
                [self.users[self._supplier_of(po)]],
                "po.submitted",
                f"新采购单 {po.number} 待确认交期",
                f"要求交期：{po.required_date:%Y-%m-%d}",
                po.get_portal_url(),
            )

    # ------------------------------------------------------------------
    def _summary(self, stats, credentials_path):
        self.stdout.write(self.style.SUCCESS("演示数据已导入"))
        self.stdout.write(f"  采购单 {PurchaseOrder.objects.count()} 张，预警 新增 {stats['opened']} 条")
        self.stdout.write("  内部员工：admin（管理员） / zhang / li")
        self.stdout.write("  供应商：huamei（华美家纺） / jiabao（嘉宝日用） / yongxing（永兴塑胶）")
        if credentials_path:
            self.stdout.write(f"  密码为随机生成，见 {credentials_path}（仅当前系统用户可读）")
        else:
            warning = f"  所有账号密码：{SIMPLE_PASSWORD}（仅限本地演示，不要用于公网）"
            self.stdout.write(self.style.WARNING(warning))
