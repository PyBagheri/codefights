from django.db import models
from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.contrib.auth.models import UserManager

from django.db.models import UniqueConstraint
from django.db.models.functions import Lower

from django.conf import settings

from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator


def validate_username(username):
    if len(username) < settings.USERNAME_MIN_LENGTH:
        error_msg = 'username must be at least 5 characters long'
    elif username.startswith('_'):
        error_msg = 'username cannot start with an underscore'
    elif not (username.isascii() and username.replace('_', '').isalnum()):
        error_msg = 'username must consist only of alphanumeric characters (latin digits only) and underscores'
    else:  # no error
        return
        
    raise ValidationError(error_msg, params={'username', username})


# This is almost identical to the default django User.
# I'm still keeping a more customizable user model for
# a potential future use.
class User(AbstractBaseUser, PermissionsMixin):
    # the default manager is sufficient for now
    objects = UserManager()
    
    username = models.CharField(max_length=50, blank=False, unique=True, validators=[validate_username])
    email = models.EmailField(max_length=255, blank=False, unique=True, validators=[EmailValidator])
    is_staff = models.BooleanField(blank=False, default=False)
    is_active = models.BooleanField(blank=False, default=False)  # inactive until email is verified
    last_login = models.DateTimeField(blank=True, null=True)  # blank until the first login
    date_joined = models.DateTimeField(blank=False, auto_now_add=True)
    
    USERNAME_FIELD = 'username'
    EMAIL_FIELD = 'email'
    
    # According to the docs, the USERNAME_FIELD and the password field
    # should not be in the REQUIRED_FIELDS, as they are always prompted for.
    # Note to self: this is only used in 'manage.py createsuperuser'.
    REQUIRED_FIELDS = ['email']
    
    def __str__(self):
        return self.username
    
    class Meta:
        constraints = [
            # Username is case-insensitive, but the cases
            # are saved as given.
            UniqueConstraint(Lower('username'), name='unique_lower_username')
        ]
