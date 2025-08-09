# your_app/forms.py

from django import forms
from .models import *

class ConsumableRequestForm(forms.ModelForm):
    class Meta:
        model = ConsumableRequest
        fields = ['file_payslpt']  # We only need to upload the payslip here

class ConsumableRequestDetailForm(forms.ModelForm):
    item = forms.ModelChoiceField(queryset=Item.objects.filter(available=True))
    
    class Meta:
        model = ConsumableRequestDetail
        fields = ['item', 'quantity', 'loan_term_months']

# Create a formset for the request details
ConsumableRequestDetailFormSet = forms.inlineformset_factory(
    ConsumableRequest,
    ConsumableRequestDetail,
    form=ConsumableRequestDetailForm,
    fields=['item', 'quantity', 'loan_term_months'],
    extra=1,
    can_delete=True
)