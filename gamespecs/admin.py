from django.contrib import admin

from gamespecs.models import GameInfo, GameTemplate, GameCodePreset, GameResult

for model in [GameInfo, GameTemplate, GameCodePreset, GameResult]:
    admin.site.register(model)
