from django.urls import path
from pages.views import GuideView, SettingsView

urlpatterns = [
    path('guide/', GuideView.as_view(), name='guide'),
    path('settings/', SettingsView.as_view(), name='settings'),
]
