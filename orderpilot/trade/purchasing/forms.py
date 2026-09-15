from django import forms
from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory

from orderpilot.trade.masterdata.models import Customer, Product, Supplier

from .models import PurchaseOrder, PurchaseOrderLine


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m-%d", **kwargs)


class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ["supplier", "customer", "owner", "order_date", "required_date", "note", "internal_note"]
        widgets = {
            "order_date": DateInput(),
            "required_date": DateInput(),
            "note": forms.Textarea(attrs={"rows": 2}),
            "internal_note": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier"].queryset = Supplier.objects.filter(is_active=True)
        self.fields["customer"].queryset = Customer.objects.filter(is_active=True)
        self.fields["owner"].queryset = get_user_model().objects.filter(user_type="internal", is_active=True)


class LineForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrderLine
        fields = ["product", "quantity", "unit_price", "note"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 已废番的商品也列出来（便于演示提交时被拦截），但标注出来
        self.fields["product"].queryset = Product.objects.order_by("status", "part_no")
        self.fields["product"].label_from_instance = lambda p: (
            f"{p.part_no} {p.name}" + ("（废番）" if p.is_discontinued else "")
        )


LineFormSet = inlineformset_factory(
    PurchaseOrder,
    PurchaseOrderLine,
    form=LineForm,
    extra=3,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class ConfirmForm(forms.Form):
    promised_date = forms.DateField(label="承诺交期", widget=DateInput())


class ReasonForm(forms.Form):
    reason = forms.CharField(label="原因", max_length=255, widget=forms.Textarea(attrs={"rows": 2}))


class ShipForm(forms.Form):
    ship_date = forms.DateField(label="出货日期", widget=DateInput())
    forwarder = forms.CharField(label="货代", max_length=100, required=False)
    tracking_no = forms.CharField(label="提单号 / 运单号", max_length=64, required=False)
    container_no = forms.CharField(label="柜号", max_length=32, required=False)
    eta = forms.DateField(label="预计到港", widget=DateInput(), required=False)
    note = forms.CharField(label="备注", max_length=200, required=False)


class DateChangeForm(forms.Form):
    new_date = forms.DateField(label="新交期", widget=DateInput())
    reason = forms.CharField(label="变更原因", max_length=255)


class MilestoneForm(forms.Form):
    planned_date = forms.DateField(label="计划日期", widget=DateInput(), required=False)
    actual_date = forms.DateField(label="实际日期", widget=DateInput(), required=False)


# 需要填写信息的状态转换
TRANSITION_FORMS = {
    "confirm": ConfirmForm,
    "reject": ReasonForm,
    "fail_inspection": ReasonForm,
    "cancel": ReasonForm,
    "ship": ShipForm,
}
