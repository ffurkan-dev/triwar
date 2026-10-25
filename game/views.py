from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def lobby(request):
    return render(request, "game/lobby.html")
