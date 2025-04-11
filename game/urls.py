from django.urls import path, include
from game.views import *

urlpatterns = [
    path("", home),
    path("online", index),
     path("play/ai/", ai_game),
    path("game/<int:id>/<str:name>/", game)
]
