from django import forms
from django.core.validators import MinValueValidator
from .models import *


class ProjectFinanceRequestForm(forms.ModelForm):
    guarantor_ippis = forms.CharField(
        max_length=50,
        label="Guarantor's IPPIS Number",
        help_text="Enter the IPPIS number of the member who will be your guarantor.",
        widget=forms.TextInput(attrs={'class': 'form-control rounded-3', 'placeholder': 'Enter IPPIS number', 'required': True})
    )

    class Meta:
        model = ProjectFinanceRequest
        fields = ['product', 'requested_amount'] 
        widgets = {
            'product': forms.TextInput(attrs={'class': 'form-control rounded-3'}),
            'requested_amount': forms.NumberInput(attrs={'class': 'form-control rounded-3'}),
        }

    def clean_guarantor_ippis(self):
        # Your existing cleaning logic
        ippis = self.cleaned_data.get('guarantor_ippis')
        try:
            guarantor_profile = Member.objects.get(ippis=ippis)
            self.cleaned_data['guarantor'] = guarantor_profile.member
        except Member.DoesNotExist:
            raise forms.ValidationError("No member found with that IPPIS number.")
        return ippis
    
class AdminProjectFinanceRequestForm(forms.ModelForm):
    class Meta:
        model = ProjectFinanceRequest
        fields = ['markup_rate', ]

        widgets = {
            'markup_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
       
        }     



class ExcelUploadForm(forms.Form):
    excel_file = forms.FileField(label='Select an Excel file', help_text='Only .xlsx files are supported.')        