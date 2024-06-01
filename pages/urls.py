from django.urls import path
from pages.views import GuideView

urlpatterns = [
    path('guide/', GuideView.as_view(), name='guide'),
]
