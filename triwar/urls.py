from django.contrib import admin
from django.shortcuts import redirect, render
from django.urls import include, path


def home(request):
    if request.user.is_authenticated:
        return redirect("lobby")
    return render(request, "home.html")


urlpatterns = [
    path("", home, name="home"),
    path("", include("accounts.urls")),
    path("", include("game.urls")),
    path("admin/", admin.site.urls),
]
