from django.urls import path
from fights.websocket.views import TestView

urlpatterns = [
    path('api1/', TestView)
]