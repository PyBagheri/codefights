from django import forms
from django.contrib.auth.password_validation import validate_password
from accounts.models import User, validate_username


class LoginForm(forms.Form):
    username_or_email = forms.CharField(
        max_length=max(User._meta.get_field('email').max_length, User._meta.get_field('username').max_length)
    )
    
    password = forms.CharField(max_length=150)


class SignUpForm(forms.Form):
    username = forms.CharField(max_length=User._meta.get_field('username').max_length, validators=[validate_username])
    
    email = forms.EmailField(max_length=User._meta.get_field('email').max_length)
    
    password = forms.CharField(max_length=150, validators=[validate_password])


class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(max_length=User._meta.get_field('email').max_length)


class ResetPasswordForm(forms.Form):
    password = forms.CharField(max_length=150, validators=[validate_password])
    
