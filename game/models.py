import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models

from .challenges import REGISTRY

ACTIVE_STATUSES = ("waiting", "active")
ROOM_TTL = timedelta(minutes=10)  # a waiting room older than this is cancelled


class Country(models.Model):
    iso2 = models.CharField(max_length=2, primary_key=True)  # same as the SVG path id
    name_tr = models.CharField(max_length=100, unique=True)
    name_en = models.CharField(max_length=100)
    continent = models.CharField(max_length=40)
    is_active = models.BooleanField(default=True)  # part of the question pool

    class Meta:
        verbose_name_plural = "countries"

    def __str__(self):
        return self.name_tr


class Match(models.Model):
    """A room and the match played in it are one record."""

    class Status(models.TextChoices):
        WAITING = "waiting", "Bekliyor"
        ACTIVE = "active", "Devam ediyor"
        FINISHED = "finished", "Bitti"
        CANCELLED = "cancelled", "İptal"

    TIME_LIMIT_CHOICES = [(20, "20 sn"), (45, "45 sn")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    host = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="hosted_matches")
    guest = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="joined_matches"
    )
    challenge_type = models.CharField(max_length=32, choices=[(k, c.label) for k, c in REGISTRY.items()])
    time_limit = models.PositiveSmallIntegerField(choices=TIME_LIMIT_CHOICES)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.WAITING)
    total_rounds = models.PositiveSmallIntegerField(default=settings.ROUNDS_PER_MATCH)
    current_round = models.PositiveSmallIntegerField(default=0)
    winner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="won_matches"
    )
    end_reason = models.CharField(max_length=12, blank=True, default="")  # "abandoned" when a player left
    host_last_seen = models.DateTimeField(null=True, blank=True)
    guest_last_seen = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["host"],
                condition=models.Q(status__in=ACTIVE_STATUSES),
                name="one_open_match_per_host",
            ),
            models.UniqueConstraint(
                fields=["guest"],
                condition=models.Q(status__in=ACTIVE_STATUSES),
                name="one_open_match_per_guest",
            ),
        ]

    def __str__(self):
        return f"{self.host} ({self.get_status_display()})"

    @property
    def challenge_label(self):
        return REGISTRY[self.challenge_type].label

    def has_player(self, user):
        return user.pk in (self.host_id, self.guest_id)

    @classmethod
    def expire_stale(cls, now):
        """Cancel waiting rooms nobody joined within ROOM_TTL."""
        cls.objects.filter(status=cls.Status.WAITING, created_at__lt=now - ROOM_TTL).update(status=cls.Status.CANCELLED)

    @classmethod
    def open_for(cls, user):
        """The user's current waiting/active match, if any."""
        return (
            cls.objects.filter(status__in=ACTIVE_STATUSES)
            .filter(models.Q(host=user) | models.Q(guest=user))
            .first()
        )


def user_stats(user):
    """Win/loss/draw counts over finished matches (leaving a match counts as a loss)."""
    played = Match.objects.filter(status=Match.Status.FINISHED).filter(models.Q(host=user) | models.Q(guest=user))
    return played.aggregate(
        wins=models.Count("id", filter=models.Q(winner=user)),
        losses=models.Count("id", filter=models.Q(winner__isnull=False) & ~models.Q(winner=user)),
        draws=models.Count("id", filter=models.Q(winner__isnull=True)),
    )


class Round(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="rounds")
    index = models.PositiveSmallIntegerField()
    payload = models.JSONField()  # question data sent to clients; never holds the answer
    answer_key = models.JSONField()  # server only
    started_at = models.DateTimeField(null=True, blank=True)
    deadline = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["index"]
        constraints = [models.UniqueConstraint(fields=["match", "index"], name="unique_round_index")]

    def __str__(self):
        return f"{self.match_id} #{self.index}"


class Answer(models.Model):
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="answers")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    value = models.CharField(max_length=100)
    is_correct = models.BooleanField()
    response_ms = models.PositiveIntegerField()
    answered_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["round", "user"], name="one_answer_per_round_and_user")]
