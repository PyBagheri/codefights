from django.urls import path
from pages.views import HomeView, GuideView, SettingsView

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('guide/', GuideView.as_view(), name='guide'),
    path('settings/', SettingsView.as_view(), name='settings'),
]
