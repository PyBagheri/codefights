from django.shortcuts import render, redirect
from django.http import Http404
from django.views.generic import View, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction

from accounts.forms import LoginForm, SignUpForm, ForgotPasswordForm, ResetPasswordForm
from accounts.models import EmailVerification
from accounts.services import (
    CheckUserUsernameAndEmailFree,
    CreateUserService,
    CreateInitialEmailVerificationService,
    CreatePasswordRecoveryEmailVerificationService,
    ResetPasswordService
)

from django.contrib.auth import login, authenticate, logout


class LoginView(View):
    template_name = 'login.html'
    
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('dashboard')
        
        return render(request, self.template_name, {})

    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('dashboard')
        
        form = LoginForm(request.POST)
        
        context = {}
        
        if not form.is_valid():
            context['form'] = form
            return render(request, self.template_name, context)
        
        user = authenticate(
            request,
            username_or_email=form.cleaned_data['username_or_email'],
            password=form.cleaned_data['password'],
        )

        if user is None:
            context['wrong_credentials'] = True
            return render(request, self.template_name, context)
        
        login(request, user)
        
        return redirect(self.request.GET.get('next', default='dashboard'))



class SignUpView(View):
    template_name = 'signup.html'
    
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('dashboard')
        
        return render(request, self.template_name, {})
    
    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('dashboard')
        
        context = {}
        
        form = SignUpForm(request.POST)
        context['form'] = form

        if not form.is_valid():
            return render(request, self.template_name, context)
        
        username = form.cleaned_data['username']
        email = form.cleaned_data['email']
        password = form.cleaned_data['password']
        
        result = CheckUserUsernameAndEmailFree(
            username=username,
            email=email
        ).execute()
        
        match result:
            case CheckUserUsernameAndEmailFree.SUCCESS:
                context['successful'] = True
                
                user = CreateUserService(
                    username=username,
                    email=email,
                    password=password
                ).execute()
                
                CreateInitialEmailVerificationService(user).execute(send_email=True)
                
            case CheckUserUsernameAndEmailFree.ERROR_USERNAME_IS_TAKEN:
                form.add_error('username', 'This username is already taken.')
            
            case CheckUserUsernameAndEmailFree.ERROR_EMAIL_IS_TAKEN:
                form.add_error('email', 'This email is already taken.')
        
        
        return render(request, self.template_name, context)


class LogoutView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        logout(request)
        
        return redirect('login')


class ForgotPasswordView(View):
    template_name = 'forgot_password.html'
    
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('dashboard')
        
        return render(request, self.template_name, {})

    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('dashboard')
        
        form = ForgotPasswordForm(request.POST)
        
        context = {}
        
        if not form.is_valid():
            context['form'] = form
            return render(request, self.template_name, context)
        
        # We ignore the possible errors.
        CreatePasswordRecoveryEmailVerificationService(
            form.cleaned_data['email']
        ).execute(send_email=True)
        
        context['email_sent'] = True
        
        return render(request, self.template_name, context)


class VerifyEmailView(View):
    template_name = 'reset_password.html'
    
    @transaction.atomic(durable=True)
    def get(self, request, *args, **kwargs):
        v = self.get_email_verification_or_404()
        
        match v.verification_type:
            case EmailVerification.VerificationTypes.INITIAL_VERIFICATION:
                v.user.activate()
                v.delete()
                return redirect('login')
                
            case EmailVerification.VerificationTypes.PASSWORD_RECOVERY:
                return render(request, self.template_name, {})

    @transaction.atomic(durable=True)
    def post(self, request, *args, **kwargs):
        v = self.get_email_verification_or_404()
        
        if v.verification_type != EmailVerification.VerificationTypes.PASSWORD_RECOVERY:
            return redirect('login')
        
        context = {}
        
        form = ResetPasswordForm(request.POST)
        
        if not form.is_valid():
            context['form'] = form
            return render(request, self.template_name, context)
        
        ResetPasswordService(
            user=v.user, password=form.cleaned_data['password']
        ).execute()
        
        v.delete()
        
        return redirect('login')

    
    def get_email_verification_or_404(self):
        v = EmailVerification.valid.select_for_update().filter(
            uuid=self.kwargs['uuid']
        ).first()
        
        if not v:
            raise Http404
        
        return v
