from django import forms

from .models import Attachment
from .services import validate_upload


class AttachmentForm(forms.Form):
    kind = forms.ChoiceField(label="类型", choices=Attachment.Kind.choices)
    file = forms.FileField(label="文件")
    note = forms.CharField(label="备注", max_length=200, required=False)

    def clean_file(self):
        f = self.cleaned_data["file"]
        validate_upload(f)
        return f
