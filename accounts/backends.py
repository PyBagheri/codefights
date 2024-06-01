from django.contrib.auth.backends import BaseBackend
from accounts.models import User

from django.db import models


class UsernameOrEmailBackend(BaseBackend):
    def authenticate(self, request, username_or_email=None, password=None):
        user = User.active.filter(
            models.Q(username=username_or_email) | models.Q(email=username_or_email)
        ).first()
        
        if not user:
            return None
        
        if user.check_password(password):
            return user
        
        return None

    def get_user(self, user_id):
        user = User.active.filter(pk=user_id).first()
        
        if not user:
            return None
        
        return user