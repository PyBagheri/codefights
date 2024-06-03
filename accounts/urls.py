from django.urls import path
from accounts.views import LoginView, SignUpView, LogoutView, ForgotPasswordView, VerifyEmailView

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    
    path('signup/', SignUpView.as_view(), name='signup'),
    
    path('logout/', LogoutView.as_view(), name='logout'),
    
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot_password'),
    
    path('verify-email/<slug:uuid>/', VerifyEmailView.as_view(), name='verify_email'),
]
