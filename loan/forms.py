from django  import forms

from .models import *




class LoanSettingsForm(forms.ModelForm):
    class Meta:
        model = LoanSettings
        fields = ['allow_loan_requests', 'allow_consumable_requests']     


class RepaymentUploadForm(forms.Form):
    excel_file = forms.FileField(
        label='Excel File',
        help_text='Upload .xlsx or .xls file with payment data',
        widget=forms.FileInput(attrs={
            'accept': '.xlsx,.xls',
            'class': 'form-control'
        })
    )
    payment_month = forms.CharField(
        label='Payment Month',
        widget=forms.TextInput(attrs={
            'type': 'month',
            'class': 'form-control',
            'required': True
        })
    )           