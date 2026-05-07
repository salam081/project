from django import forms
from django.forms import modelformset_factory, BaseModelFormSet
from .models import StockIn, ReceivedItem
from decimal import Decimal


class StockInForm(forms.ModelForm):
    class Meta:
        model = StockIn
        fields = ['supplier', 'note']
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'note': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class ReceivedItemForm(forms.ModelForm):
    """Individual item form with styling and field-level validation."""

    class Meta:
        model = ReceivedItem
        fields = ('brand', 'model_name', 'quantity', 'unit_price','brand_image')
        widgets = {
            'brand': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Samsung',
            }),
            'model_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Galaxy S24',
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
            }),
            'unit_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'step': '0.01',
                'placeholder': '0.00',
            }),
             'brand_image': forms.FileInput(attrs={
                'class': 'form-control',
            }),
        }

    def clean_quantity(self):
        qty = self.cleaned_data.get('quantity')
        if qty is not None and qty <= 0:
            raise forms.ValidationError("Quantity must be at least 1.")
        return qty

   

    def clean_unit_price(self):
        price = self.cleaned_data.get('unit_price')
        if price is not None and price <= Decimal('0.00'):
            raise forms.ValidationError("Unit price must be greater than zero.")
        return price


class BaseReceivedItemFormSet(BaseModelFormSet):
    """FIX 2: Formset-level validation — ensures at least one item is submitted."""

    def clean(self):
        if any(self.errors):
            # Skip cross-form validation if individual forms already have errors
            return

        # Count forms that have data and are not marked for deletion
        filled_forms = [
            form for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False)
        ]

        if not filled_forms:
            raise forms.ValidationError(
                "You must add at least one item to the stock entry."
            )

# Remove the redundant fields= argument
ReceivedItemFormSet = modelformset_factory(
    ReceivedItem,
    form=ReceivedItemForm,
    formset=BaseReceivedItemFormSet,
    extra=1,
    min_num=1,
    validate_min=True,
    can_delete=True,
)