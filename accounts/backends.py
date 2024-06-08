from django.contrib.auth.backends import BaseBackend
from accounts.models import User

from django.db import models


class UsernameOrEmailBackend(BaseBackend):
    def authenticate(self, request, username=None, username_or_email=None, password=None):
        if username is None and username_or_email is None:
            raise ValueError("at least one of 'username' or 'username_or_email' must be given")
        
        if username_or_email is None:
            username_or_email = username
        
        user = User.active.filter(
            models.Q(username=username_or_email) | models.Q(email=username_or_email)
        ).first()
        
        if not user:
            User().set_password(password)  # see ModelBackend's comments.
            return None
        
        if user.check_password(password):
            return user
        
        return None

    def get_user(self, user_id):
        user = User.active.filter(pk=user_id).first()
        
        if not user:
            return None
        
        return user