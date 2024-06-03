from django import forms
from django.core.exceptions import ValidationError


class BeforeAfterUUIDForm(forms.Form):
    before = forms.UUIDField(required=False)
    after = forms.UUIDField(required=False)
    
    def clean(self):
        cleaned_data = super().clean()
        
        # When none of 'before' or 'after' is given, that would
        # be the first page.
        if cleaned_data['before'] and cleaned_data['after']:
            raise ValidationError("Exactly one of the field 'before' or 'after' must be given")

        return cleaned_data
