from django.contrib import admin

from fights.models import Fight, PlayerFight, Invitation, Hosting

for model in [PlayerFight, Hosting]:
    admin.site.register(model)


class FightAdmin(admin.ModelAdmin):
    readonly_fields = ('uuid',)


class InvitationAdmin(admin.ModelAdmin):
    readonly_fields = ('uuid',)


for i in [(Fight, FightAdmin), (Invitation, InvitationAdmin)]:
    admin.site.register(*i)
