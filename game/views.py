from functools import lru_cache

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.safestring import mark_safe

from .challenges import REGISTRY
from .models import Match


@login_required
def lobby(request):
    open_match = Match.open_for(request.user)
    open_url = None
    if open_match:
        name = "room_wait" if open_match.status == Match.Status.WAITING else "match"
        open_url = reverse(name, args=[open_match.id])
    return render(
        request,
        "game/lobby.html",
        {
            "challenges": [(c.key, c.label) for c in REGISTRY.values()],
            "time_limits": Match.TIME_LIMIT_CHOICES,
            "open_url": open_url,
        },
    )


@login_required
def room_wait(request, match_id):
    match = get_object_or_404(Match, pk=match_id)
    if match.host_id != request.user.pk:
        raise Http404
    if match.status == Match.Status.ACTIVE:
        return redirect("match", match_id=match.id)
    if match.status != Match.Status.WAITING:
        return redirect("lobby")
    return render(request, "game/room_wait.html", {"match": match})


@login_required
def match_page(request, match_id):
    match = get_object_or_404(Match.objects.select_related("host", "guest"), pk=match_id)
    if not match.has_player(request.user):
        raise Http404
    if match.status == Match.Status.WAITING:
        return redirect("room_wait", match_id=match.id)
    return render(request, "game/match.html", {"match": match})


@lru_cache(maxsize=1)
def _world_svg():
    return mark_safe((settings.BASE_DIR / "static" / "maps" / "world.svg").read_text(encoding="utf-8"))


@login_required
def practice(request):
    return render(request, "game/practice.html", {"world_svg": _world_svg()})
