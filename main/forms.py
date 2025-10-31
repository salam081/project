# forms.py
from django import forms
from .models import Popup

class PopupForm(forms.ModelForm):
    class Meta:
        model = Popup
        # Exclude 'created_at' since it's auto_now_add
        fields = ['title', 'message', 'link_url', 'is_active', 'start_date', 'end_date'] 
        widgets = {
            # Use appropriate widgets for date/time input in HTML
            'start_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }