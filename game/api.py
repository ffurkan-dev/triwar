import json
from functools import wraps

from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .challenges import REGISTRY
from .models import Match


def api_login_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Giriş yapmalısın."}, status=401)
        return view(request, *args, **kwargs)

    return wrapper


def error(message, status):
    return JsonResponse({"error": message}, status=status)


def room_json(match):
    return {
        "id": str(match.id),
        "host_username": match.host.username,
        "challenge_label": match.challenge_label,
        "time_limit": match.time_limit,
        "created_at": match.created_at.isoformat(),
    }


@api_login_required
@require_http_methods(["GET", "POST"])
def rooms(request):
    if request.method == "GET":
        waiting = (
            Match.objects.filter(status=Match.Status.WAITING)
            .exclude(host=request.user)
            .select_related("host")
            .order_by("-created_at")
        )
        return JsonResponse({"rooms": [room_json(m) for m in waiting]})

    try:
        data = json.loads(request.body or b"{}")
        challenge_type = data["challenge_type"]
        time_limit = int(data["time_limit"])
    except (ValueError, KeyError, TypeError):
        return error("Geçersiz istek.", 400)
    if challenge_type not in REGISTRY or time_limit not in dict(Match.TIME_LIMIT_CHOICES):
        return error("Geçersiz mücadele türü veya süre.", 400)

    with transaction.atomic():
        existing = Match.open_for(request.user)
        if existing:
            return error("Zaten açık bir odan veya maçın var.", 409)
        try:
            with transaction.atomic():
                match = Match.objects.create(host=request.user, challenge_type=challenge_type, time_limit=time_limit)
        except IntegrityError:
            return error("Zaten açık bir odan veya maçın var.", 409)
    return JsonResponse({"id": str(match.id), "url": reverse("room_wait", args=[match.id])}, status=201)


@api_login_required
@require_http_methods(["GET"])
def room_detail(request, match_id):
    match = get_object_or_404(Match, pk=match_id)
    if not match.has_player(request.user):
        return error("Bulunamadı.", 404)
    data = {"status": match.status}
    if match.status == Match.Status.ACTIVE:
        data["match_url"] = reverse("match", args=[match.id])
    return JsonResponse(data)


@api_login_required
@require_http_methods(["POST"])
def room_join(request, match_id):
    with transaction.atomic():
        match = get_object_or_404(Match.objects.select_for_update(), pk=match_id)
        if match.host_id == request.user.pk:
            return error("Kendi odana katılamazsın.", 403)
        if match.status != Match.Status.WAITING or match.guest_id is not None:
            return error("Oda doldu.", 409)
        if Match.open_for(request.user):
            return error("Zaten açık bir odan veya maçın var.", 409)
        match.guest = request.user
        match.status = Match.Status.ACTIVE
        match.started_at = timezone.now()
        try:
            with transaction.atomic():
                match.save(update_fields=["guest", "status", "started_at"])
        except IntegrityError:
            return error("Zaten açık bir odan veya maçın var.", 409)
    return JsonResponse({"url": reverse("match", args=[match.id])})


@api_login_required
@require_http_methods(["POST"])
def room_cancel(request, match_id):
    with transaction.atomic():
        match = get_object_or_404(Match.objects.select_for_update(), pk=match_id)
        if match.host_id != request.user.pk:
            return error("Bu odayı iptal edemezsin.", 403)
        if match.status != Match.Status.WAITING:
            return error("Oda artık beklemiyor.", 409)
        match.status = Match.Status.CANCELLED
        match.save(update_fields=["status"])
    return JsonResponse({"ok": True})


# Single-player map check (dev tool): the answer stays in the session until it is checked.
@api_login_required
@require_http_methods(["GET"])
def practice_question(request):
    challenge = REGISTRY["country_map"]
    payload, answer_key = challenge.generate_rounds(1)[0]
    request.session["practice_answer"] = answer_key
    return JsonResponse({"payload": payload})


@api_login_required
@require_http_methods(["POST"])
def practice_answer(request):
    answer_key = request.session.pop("practice_answer", None)
    if answer_key is None:
        return error("Soru bulunamadı.", 409)
    try:
        value = str(json.loads(request.body or b"{}")["value"])
    except (ValueError, KeyError, TypeError):
        return error("Geçersiz istek.", 400)
    correct = REGISTRY["country_map"].check_answer(answer_key, value)
    return JsonResponse({"correct": correct, "answer": answer_key["answer"]})
