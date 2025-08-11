# your_app/forms.py
from django import forms
from django.core.validators import MinValueValidator
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


#used

class AdminUpdateConsumableRequestForm(forms.Form):
    loan_term_months = forms.IntegerField(
        label="Loan Term (months)",
        validators=[MinValueValidator(1, "Loan term must be at least 1 month.")],
        help_text="Enter the new loan term in months.",
        required=True
    )
    quantity = forms.IntegerField(
        label="Quantity",
        validators=[MinValueValidator(1, "Quantity must be at least 1.")],
        help_text="Enter the updated quantity.",
        required=False
    )
    item_price = forms.DecimalField(
        label="Item Price",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0, "Item price cannot be negative.")],
        help_text="Enter the updated item price.",
        required=False
    )
    detail_id = forms.IntegerField(
        widget=forms.HiddenInput(),
        required=True
    )