from django.test import TestCase
from django.urls import reverse

from .models import User

VALID = {
    "email": "deniz@example.com",
    "username": "deniz",
    "password1": "S3cure-pass-42",
    "password2": "S3cure-pass-42",
}


class RegisterTests(TestCase):
    def test_register_logs_in_and_redirects_to_lobby(self):
        resp = self.client.post(reverse("register"), VALID)
        self.assertRedirects(resp, reverse("lobby"))
        self.assertTrue(User.objects.filter(email="deniz@example.com").exists())
        self.assertEqual(self.client.get(reverse("lobby")).status_code, 200)

    def test_duplicate_email_case_insensitive(self):
        User.objects.create_user(email="deniz@example.com", username="other", password="x")
        resp = self.client.post(reverse("register"), {**VALID, "email": "DENIZ@example.com"})
        self.assertContains(resp, "Bu e-posta ile zaten bir hesap var.")
        self.assertEqual(User.objects.count(), 1)

    def test_duplicate_username_case_insensitive(self):
        User.objects.create_user(email="a@example.com", username="Deniz", password="x")
        resp = self.client.post(reverse("register"), VALID)
        self.assertContains(resp, "Bu kullanıcı adı alınmış.")
        self.assertEqual(User.objects.count(), 1)

    def test_password_mismatch(self):
        resp = self.client.post(reverse("register"), {**VALID, "password2": "different-pass-1"})
        self.assertContains(resp, "Şifreler eşleşmiyor.")

    def test_weak_password_rejected(self):
        resp = self.client.post(reverse("register"), {**VALID, "password1": "12345678", "password2": "12345678"})
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(resp.status_code, 200)

    def test_invalid_username(self):
        resp = self.client.post(reverse("register"), {**VALID, "username": "a b"})
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(resp.status_code, 200)


class LoginLogoutTests(TestCase):
    def setUp(self):
        User.objects.create_user(email="deniz@example.com", username="deniz", password="S3cure-pass-42")

    def test_login_with_email_case_insensitive(self):
        resp = self.client.post(reverse("login"), {"username": "Deniz@Example.com", "password": "S3cure-pass-42"})
        self.assertRedirects(resp, reverse("lobby"))

    def test_login_wrong_password(self):
        resp = self.client.post(reverse("login"), {"username": "deniz@example.com", "password": "nope"})
        self.assertContains(resp, "E-posta veya şifre hatalı.")

    def test_logout_requires_post(self):
        self.client.login(email="deniz@example.com", password="S3cure-pass-42")
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.client.post(reverse("logout"))
        self.assertEqual(self.client.get(reverse("lobby")).status_code, 302)

    def test_lobby_requires_login(self):
        resp = self.client.get(reverse("lobby"))
        self.assertRedirects(resp, f"{reverse('login')}?next={reverse('lobby')}")

    def test_navbar_shows_only_username(self):
        self.client.login(email="deniz@example.com", password="S3cure-pass-42")
        resp = self.client.get(reverse("lobby"))
        self.assertContains(resp, "deniz")
        self.assertNotContains(resp, "deniz@example.com")
