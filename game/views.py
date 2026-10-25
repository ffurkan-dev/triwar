from functools import lru_cache

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe

from . import engine
from .challenges import REGISTRY
from .models import Country, Match, user_stats


@login_required
def lobby(request):
    Match.expire_stale(timezone.now())
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
            "my_stats": user_stats(request.user),
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
    if match.status == Match.Status.FINISHED:
        return redirect("match_result", match_id=match.id)
    return render(request, "game/match.html", {"match": match, "world_svg": _world_svg()})


@login_required
def match_result(request, match_id):
    match = get_object_or_404(Match.objects.select_related("host", "guest", "winner"), pk=match_id)
    if not match.has_player(request.user):
        raise Http404
    if match.status != Match.Status.FINISHED:
        return redirect("match", match_id=match.id)
    s = engine.scores(match)
    me, opponent = (match.host, match.guest) if match.host_id == request.user.pk else (match.guest, match.host)
    if match.winner_id is None:
        outcome = "draw"
    else:
        outcome = "win" if match.winner_id == request.user.pk else "loss"
    rounds = _round_summaries(match, request.user)
    return render(
        request,
        "game/result.html",
        {
            "rounds": rounds,
            "abandoned": match.end_reason == "abandoned",
            "match": match,
            "me": me,
            "opponent": opponent,
            "me_score": s[me.pk]["score"],
            "opponent_score": s[opponent.pk]["score"],
            "outcome": outcome,
        },
    )


@lru_cache(maxsize=1)
def _world_svg():
    return mark_safe((settings.BASE_DIR / "static" / "maps" / "world.svg").read_text(encoding="utf-8"))


@login_required
def practice(request):
    return render(request, "game/practice.html", {"world_svg": _world_svg()})


def _round_summaries(match, user):
    """One entry per closed round: the country and what each player answered."""
    rounds = list(match.rounds.filter(closed_at__isnull=False).prefetch_related("answers"))
    countries = Country.objects.in_bulk([r.answer_key["iso2"] for r in rounds])

    def describe(answer):
        if answer is None:
            return None
        return {"value": answer.value, "correct": answer.is_correct, "seconds": answer.response_ms / 1000}

    summaries = []
    for rnd in rounds:
        answers = {a.user_id: a for a in rnd.answers.all()}
        opponent_id = match.guest_id if user.pk == match.host_id else match.host_id
        summaries.append(
            {
                "number": rnd.index + 1,
                "iso2": rnd.answer_key["iso2"],
                "country": countries[rnd.answer_key["iso2"]].name_tr,
                "me": describe(answers.get(user.pk)),
                "opponent": describe(answers.get(opponent_id)),
            }
        )
    return summaries
