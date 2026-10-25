import uuid

from django.conf import settings
from django.db import models

from .challenges import REGISTRY

ACTIVE_STATUSES = ("waiting", "active")


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
    def open_for(cls, user):
        """The user's current waiting/active match, if any."""
        return (
            cls.objects.filter(status__in=ACTIVE_STATUSES)
            .filter(models.Q(host=user) | models.Q(guest=user))
            .first()
        )
