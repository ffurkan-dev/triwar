from django.urls import path

from . import api, views

urlpatterns = [
    path("lobby/", views.lobby, name="lobby"),
    path("room/<uuid:match_id>/", views.room_wait, name="room_wait"),
    path("match/<uuid:match_id>/", views.match_page, name="match"),
    path("practice/", views.practice, name="practice"),
    path("api/practice/question/", api.practice_question, name="api_practice_question"),
    path("api/practice/answer/", api.practice_answer, name="api_practice_answer"),
    path("api/rooms/", api.rooms, name="api_rooms"),
    path("api/rooms/<uuid:match_id>/", api.room_detail, name="api_room_detail"),
    path("api/rooms/<uuid:match_id>/join/", api.room_join, name="api_room_join"),
    path("api/rooms/<uuid:match_id>/cancel/", api.room_cancel, name="api_room_cancel"),
]
