from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models


class User(AbstractUser):
    """Login is by e-mail; the username is the only public identity."""

    email = models.EmailField(unique=True)
    username = models.CharField(
        max_length=20,
        unique=True,
        validators=[RegexValidator(r"^[A-Za-z0-9_]{3,20}$", "3-20 karakter; harf, rakam ve alt çizgi.")],
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]
