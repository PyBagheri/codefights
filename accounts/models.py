from django.db import models
from django.contrib.auth import models as auth_models

from django.db.models import UniqueConstraint
from django.db.models.functions import Lower

from django.conf import settings

from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator

from django.utils import timezone
from datetime import timedelta

from django.urls import reverse

import uuid


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


class UserQuerySet(models.QuerySet):   
    def from_username_list(self, username_list):
        return self.filter(username__in=username_list)
    
    def from_email(self, email):
        return self.filter(email=email).first()


class ActiveUserManager(auth_models.UserManager):
    use_in_migrations = False
    
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class DefaultUserManager(auth_models.UserManager.from_queryset(UserQuerySet)):
    pass


# This is almost identical to the default django User.
# I'm still keeping a more customizable user model for
# a potential future use.
class User(auth_models.AbstractBaseUser, auth_models.PermissionsMixin):
    objects = DefaultUserManager()
    active = ActiveUserManager.from_queryset(UserQuerySet)()
    
    username = models.CharField(max_length=50, blank=False, unique=True, validators=[validate_username])
    email = models.EmailField(max_length=255, blank=False, unique=True, validators=[EmailValidator])
    is_staff = models.BooleanField(blank=False, default=False)
    
    # NOTE: We currently only use this field to check if a user has
    # validated their email or not. If you want to use it for other
    # purposes, you MUST change the services, views, ... that use
    # it with that assupmtion, or just create another field.
    is_active = models.BooleanField(blank=False, default=False)  # inactive until email is verified
    
    last_login = models.DateTimeField(blank=True, null=True)  # blank until the first login
    date_joined = models.DateTimeField(blank=False, auto_now_add=True)
    
    USERNAME_FIELD = 'username'
    EMAIL_FIELD = 'email'
    
    # According to the docs, the USERNAME_FIELD and the password field
    # should not be in the REQUIRED_FIELDS, as they are always prompted for.
    # Note to self: this is only used in 'manage.py createsuperuser'.
    REQUIRED_FIELDS = ['email']
    
    def activate(self):
        self.is_active = True
        self.save()
    
    def __str__(self):
        return f'{self.id}. {self.username}'
    
    class Meta:
        constraints = [
            # Username is case-insensitive, but the cases
            # are saved as given.
            UniqueConstraint(Lower('username'), name='unique_lower_username')
        ]


class EmailVerificationQuerySet(models.QuerySet):
    def from_uuid(self, uuid):
        try:
            return self.filter(uuid=uuid).first()
        except ValidationError:
            return self.none()
    


class ValidEmailVerificationManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(
            expires_at__gt=timezone.now()
        )


def get_email_verification_expiry():
    return timezone.now() + timedelta(minutes=settings.EMAIL_VERIFICATION_EXPIRY_MINUTES)


class EmailVerification(models.Model):
    class VerificationTypes(models.TextChoices):
        INITIAL_VERIFICATION = 'I', 'Initial Verification'
        PASSWORD_RECOVERY = 'P', 'Password Recovery'
    
    class Meta:
        indexes = [
            models.Index('uuid', name='email_verification_uuid_idx')
        ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    
    verification_type = models.CharField(choices=VerificationTypes, max_length=1)
    
    expires_at = models.DateTimeField(default=get_email_verification_expiry)
    
    def get_absolute_url(self):
        return reverse('verify_email', kwargs={'uuid': self.uuid.hex})
    
    
    def __str__(self):
        return f'{self.id}. {self.get_verification_type_display()} (@{self.user.username}) until {self.expires_at.strftime("%Y/%m/%d %H:%M:%S")}'
    
    objects = models.Manager.from_queryset(EmailVerificationQuerySet)()
    valid = ValidEmailVerificationManager.from_queryset(EmailVerificationQuerySet)()
