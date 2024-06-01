from accounts.models import User, EmailVerification
from django.db import models


class CheckUserUsernameAndEmailFree:
    # Results
    SUCCESS = 0
    ERROR_USERNAME_IS_TAKEN = 1
    ERROR_EMAIL_IS_TAKEN = 2
    
    
    def __init__(self, *, username, email) -> None:
        self.username = username
        self.email = email
    
    def execute(self):
        user = User.objects.filter(
            models.Q(username=self.username) | models.Q(email=self.email)
        ).only('username', 'email').first()
        
        if not user:
            return CheckUserUsernameAndEmailFree.SUCCESS
        
        if user.username == self.username:
            return CheckUserUsernameAndEmailFree.ERROR_USERNAME_IS_TAKEN
        
        if user.email == self.email:
            return CheckUserUsernameAndEmailFree.ERROR_EMAIL_IS_TAKEN


class CreateUserService:
    def __init__(self, *, username, email, password):
        self.username = username
        self.email = email
        self.password = password
    
    def execute(self):
        return User.objects.create_user(
            username=self.username,
            email=self.email,
            password=self.password
        )


class CreateInitialEmailVerificationService:
    def __init__(self, user):
        self.user = user
    
    def execute(self, send_email=False):
        v = EmailVerification.objects.create(
            user=self.user,
            verification_type=EmailVerification.VerificationTypes.INITIAL_VERIFICATION
        )
        
        if send_email:
            self.user.email
            v.uuid.hex


class CreatePasswordRecoveryEmailVerificationService:
    # Results
    SUCCESS = 0
    ERROR_NO_USER_WITH_THAT_EMAIL = 1
    
    def __init__(self, email):
        self.email = email
    
    def execute(self, send_email=False):
        # NOTE: We let both active and inactive players to be able
        # to verify their email and thus ACTIVATE their account through
        # the forgot password form. If the is_active form is used for
        # other purposes too, this must be changed accordingly.
        user = User.objects.from_email(self.email)
        
        if not user:
            return CreatePasswordRecoveryEmailVerificationService.ERROR_NO_USER_WITH_THAT_EMAIL
        
        v = EmailVerification.objects.create(
            user=user,
            verification_type=EmailVerification.VerificationTypes.PASSWORD_RECOVERY
        )
        
        if send_email:
            v.user.email
            v.uuid.hex

        return CreatePasswordRecoveryEmailVerificationService.SUCCESS


class ResetPasswordService:
    def __init__(self, *, user, password):
        self.user = user
        self.password = password
    
    def execute(self):
        self.user.set_password(self.password)
        
        # See the comments for the is_active field on the User model.
        self.user.activate()
