from django.urls import path
from accounts.views import LoginView, SignUpView, ForgotPasswordView, SettingsView, VerifyEmailView

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    
    path('signup/', SignUpView.as_view(), name='signup'),
    
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot_password'),
    
    path('verify-email/<slug:uuid>/', VerifyEmailView.as_view(), name='verify-email'),
    
    path('settings/', SettingsView.as_view(), name='settings'),
]
