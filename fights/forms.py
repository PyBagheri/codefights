from django import forms
from django.core.exceptions import ValidationError
from django.conf import settings

from accounts.models import User


def code_max_upload_size_validator(file):
    if file.size > settings.MAX_CODE_UPLOAD_SIZE:
        raise ValidationError(f'Uploaded code size cannot be larger than {settings.MAX_CODE_UPLOAD_SIZE // 1000} KB')


def usernames_list_json_validator(json):
    """Validate a JSON object to ensure that it's an array of strings."""
    
    if not isinstance(json, list):
        raise ValidationError('%(usernames_list)s is not an array',
                              params={'usernames_list': json})
    
    for item in json:
        if not isinstance(item, str):
            raise ValidationError('usernames list must only consist of strings',
                                  params={'usernames_list': json})



class CreateFightForm(forms.Form):
    is_public = forms.BooleanField(required=False)
    usernames_list = forms.JSONField(validators=[usernames_list_json_validator])
    code = forms.FileField(validators=[code_max_upload_size_validator])


class AcceptInvitationForm(forms.Form):
    code = forms.FileField(validators=[code_max_upload_size_validator])


class SearchPlayerToInviteAPIForm(forms.Form):
    username = forms.CharField(max_length=User._meta.get_field('username').max_length)


# Used for certain action views that only need a URL and the user
# session and no further data. To avoid accidental requests on these
# URLs, we post a non-empty confirmation text.
class ConfirmationForm(forms.Form):
    confirmed = forms.BooleanField(required=False, initial=False)
