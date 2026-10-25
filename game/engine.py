"""Lazy match state machine.

There is no background worker: every state poll and every answer calls `advance`,
which looks at the timestamps and moves the match forward. Callers hold a row lock
on the match (`select_for_update` inside `transaction.atomic`). `now` is always a
parameter so time-dependent behaviour can be tested.
"""
from datetime import timedelta

from django.db import IntegrityError, transaction

from .challenges import REGISTRY
from .models import Answer, Match, Round

COUNTDOWN_SECONDS = 3  # "3-2-1" before the first question
REVEAL_SECONDS = 3  # answer reveal between rounds
ANSWER_TOLERANCE_SECONDS = 1  # network slack for answers right at the deadline


class EngineError(Exception):
    def __init__(self, message, status):
        super().__init__(message)
        self.message = message
        self.status = status


def start_match(match, now):
    """Generate all rounds; the first one starts after the countdown."""
    challenge = REGISTRY[match.challenge_type]
    generated = challenge.generate_rounds(match.total_rounds)
    Round.objects.bulk_create(
        Round(match=match, index=i, payload=payload, answer_key=key) for i, (payload, key) in enumerate(generated)
    )
    first = match.rounds.get(index=0)
    first.started_at = now + timedelta(seconds=COUNTDOWN_SECONDS)
    first.deadline = first.started_at + timedelta(seconds=match.time_limit)
    first.save(update_fields=["started_at", "deadline"])


def current_round(match):
    return match.rounds.get(index=match.current_round)


def advance(match, now):
    """Close the open round, start the next one or finish the match, as time dictates."""
    if match.status != Match.Status.ACTIVE:
        return
    total = match.rounds.count()
    while True:
        rnd = current_round(match)
        if rnd.closed_at is None:
            answered_at = [a.answered_at for a in rnd.answers.all()]
            if len(answered_at) >= 2:
                rnd.closed_at = max(answered_at)
            elif now >= rnd.deadline:
                rnd.closed_at = rnd.deadline
            else:
                return
            rnd.save(update_fields=["closed_at"])
        reveal_end = rnd.closed_at + timedelta(seconds=REVEAL_SECONDS)
        if now < reveal_end:
            return
        if match.current_round + 1 >= total:
            finish_match(match, reveal_end)
            return
        match.current_round += 1
        match.save(update_fields=["current_round"])
        nxt = current_round(match)
        nxt.started_at = reveal_end
        nxt.deadline = reveal_end + timedelta(seconds=match.time_limit)
        nxt.save(update_fields=["started_at", "deadline"])


def scores(match):
    """{user_id: {"score": correct answers, "ms": total time of correct answers}} over closed rounds."""
    result = {match.host_id: {"score": 0, "ms": 0}, match.guest_id: {"score": 0, "ms": 0}}
    answers = Answer.objects.filter(round__match=match, round__closed_at__isnull=False, is_correct=True)
    for answer in answers:
        entry = result[answer.user_id]
        entry["score"] += 1
        entry["ms"] += answer.response_ms
    return result


def pick_winner(match):
    """Higher score wins; a tie goes to the lower total time of correct answers; else a draw (None)."""
    s = scores(match)
    host, guest = s[match.host_id], s[match.guest_id]
    if host["score"] != guest["score"]:
        return match.host if host["score"] > guest["score"] else match.guest
    if host["ms"] != guest["ms"]:
        return match.host if host["ms"] < guest["ms"] else match.guest
    return None


def finish_match(match, now):
    match.status = Match.Status.FINISHED
    match.finished_at = now
    match.winner = pick_winner(match)
    match.save(update_fields=["status", "finished_at", "winner"])


def submit_answer(match, user, round_index, value, now):
    """Validate and store an answer. Raises EngineError when it must be rejected."""
    # Settle the match as of a moment ago, so an answer just past the deadline can still land.
    advance(match, now - timedelta(seconds=ANSWER_TOLERANCE_SECONDS))
    if match.status != Match.Status.ACTIVE:
        raise EngineError("Maç bitti.", 409)
    if round_index != match.current_round:
        raise EngineError("Bu tur kapandı.", 409)
    rnd = current_round(match)
    if rnd.closed_at is not None:
        raise EngineError("Bu tur kapandı.", 409)
    if now < rnd.started_at:
        raise EngineError("Tur henüz başlamadı.", 409)
    if now > rnd.deadline + timedelta(seconds=ANSWER_TOLERANCE_SECONDS):
        raise EngineError("Süre doldu.", 409)
    if value not in rnd.payload["options"]:
        raise EngineError("Geçersiz cevap.", 400)
    if rnd.answers.filter(user=user).exists():
        raise EngineError("Bu tura zaten cevap verdin.", 409)

    elapsed_ms = int((now - rnd.started_at).total_seconds() * 1000)
    try:
        with transaction.atomic():
            answer = Answer.objects.create(
                round=rnd,
                user=user,
                value=value,
                is_correct=REGISTRY[match.challenge_type].check_answer(rnd.answer_key, value),
                response_ms=max(0, min(elapsed_ms, match.time_limit * 1000)),
                answered_at=now,
            )
    except IntegrityError:
        raise EngineError("Bu tura zaten cevap verdin.", 409)
    advance(match, now)
    return answer
