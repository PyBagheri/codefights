from django.contrib import admin

from accounts.models import User, EmailVerification

class EmailVerificationAdmin(admin.ModelAdmin):
    readonly_fields = ('uuid',)

admin.site.register(User)
admin.site.register(EmailVerification, EmailVerificationAdmin)
