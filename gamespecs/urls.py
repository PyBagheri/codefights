from django.urls import path

from gamespecs.views import GamesListView, GameDetailsView

urlpatterns = [
    path('', GamesListView.as_view(), name='games_list'),
    path('<slug:slug>/', GameDetailsView.as_view(), name='game_details')
]
