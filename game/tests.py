import json

from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from .challenges import REGISTRY
from .models import Match


def make_user(name):
    return User.objects.create_user(email=f"{name}@example.com", username=name, password="S3cure-pass-42")


class ApiTestCase(TestCase):
    def setUp(self):
        self.deniz = make_user("deniz")
        self.kaan = make_user("kaan")
        self.ece = make_user("ece")

    def as_user(self, user):
        self.client.force_login(user)

    def post_json(self, url, data=None):
        return self.client.post(url, json.dumps(data or {}), content_type="application/json")

    def create_room(self, user, time_limit=20):
        self.as_user(user)
        resp = self.post_json(reverse("api_rooms"), {"challenge_type": "country_map", "time_limit": time_limit})
        self.assertEqual(resp.status_code, 201, resp.content)
        return Match.objects.get(pk=resp.json()["id"])


class RoomCreateTests(ApiTestCase):
    def test_create_room(self):
        match = self.create_room(self.deniz, 45)
        self.assertEqual(match.host, self.deniz)
        self.assertEqual(match.status, Match.Status.WAITING)
        self.assertEqual(match.time_limit, 45)

    def test_invalid_input(self):
        self.as_user(self.deniz)
        for payload in ({"challenge_type": "nope", "time_limit": 20}, {"challenge_type": "country_map", "time_limit": 30}, {}):
            resp = self.post_json(reverse("api_rooms"), payload)
            self.assertEqual(resp.status_code, 400)

    def test_only_one_open_match(self):
        self.create_room(self.deniz)
        resp = self.post_json(reverse("api_rooms"), {"challenge_type": "country_map", "time_limit": 20})
        self.assertEqual(resp.status_code, 409)

    def test_guest_in_active_match_cannot_create(self):
        match = self.create_room(self.deniz)
        self.as_user(self.kaan)
        self.post_json(reverse("api_room_join", args=[match.id]))
        resp = self.post_json(reverse("api_rooms"), {"challenge_type": "country_map", "time_limit": 20})
        self.assertEqual(resp.status_code, 409)

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("api_rooms")).status_code, 401)
        self.assertEqual(self.post_json(reverse("api_rooms")).status_code, 401)


class RoomListTests(ApiTestCase):
    def test_list_excludes_own_and_leaks_no_email(self):
        self.create_room(self.deniz)
        self.as_user(self.kaan)
        resp = self.client.get(reverse("api_rooms"))
        rooms = resp.json()["rooms"]
        self.assertEqual(len(rooms), 1)
        self.assertEqual(rooms[0]["host_username"], "deniz")
        self.assertEqual(rooms[0]["challenge_label"], REGISTRY["country_map"].label)
        self.assertEqual(rooms[0]["time_limit"], 20)
        self.assertNotIn("example.com", resp.content.decode())
        self.as_user(self.deniz)
        self.assertEqual(self.client.get(reverse("api_rooms")).json()["rooms"], [])

    def test_only_waiting_rooms_listed(self):
        match = self.create_room(self.deniz)
        self.as_user(self.kaan)
        self.post_json(reverse("api_room_join", args=[match.id]))
        self.as_user(self.ece)
        self.assertEqual(self.client.get(reverse("api_rooms")).json()["rooms"], [])


class JoinCancelTests(ApiTestCase):
    def test_join_starts_match(self):
        match = self.create_room(self.deniz)
        self.as_user(self.kaan)
        resp = self.post_json(reverse("api_room_join", args=[match.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["url"], reverse("match", args=[match.id]))
        match.refresh_from_db()
        self.assertEqual(match.status, Match.Status.ACTIVE)
        self.assertEqual(match.guest, self.kaan)
        self.assertIsNotNone(match.started_at)

    def test_cannot_join_own_room(self):
        match = self.create_room(self.deniz)
        resp = self.post_json(reverse("api_room_join", args=[match.id]))
        self.assertEqual(resp.status_code, 403)

    def test_second_joiner_gets_409(self):
        match = self.create_room(self.deniz)
        self.as_user(self.kaan)
        self.assertEqual(self.post_json(reverse("api_room_join", args=[match.id])).status_code, 200)
        self.as_user(self.ece)
        resp = self.post_json(reverse("api_room_join", args=[match.id]))
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()["error"], "Oda doldu.")
        match.refresh_from_db()
        self.assertEqual(match.guest, self.kaan)

    def test_cannot_join_while_in_another_match(self):
        first = self.create_room(self.deniz)
        second = self.create_room(self.kaan)
        self.as_user(self.ece)
        self.post_json(reverse("api_room_join", args=[first.id]))
        resp = self.post_json(reverse("api_room_join", args=[second.id]))
        self.assertEqual(resp.status_code, 409)

    def test_cannot_join_while_hosting(self):
        self.create_room(self.deniz)
        other = self.create_room(self.kaan)
        self.as_user(self.deniz)
        resp = self.post_json(reverse("api_room_join", args=[other.id]))
        self.assertEqual(resp.status_code, 409)

    def test_cancel(self):
        match = self.create_room(self.deniz)
        resp = self.post_json(reverse("api_room_cancel", args=[match.id]))
        self.assertEqual(resp.status_code, 200)
        match.refresh_from_db()
        self.assertEqual(match.status, Match.Status.CANCELLED)
        self.as_user(self.kaan)
        self.assertEqual(self.post_json(reverse("api_room_join", args=[match.id])).status_code, 409)
        self.create_room(self.deniz)  # host is free to open a new room

    def test_only_host_can_cancel_and_only_while_waiting(self):
        match = self.create_room(self.deniz)
        self.as_user(self.kaan)
        self.assertEqual(self.post_json(reverse("api_room_cancel", args=[match.id])).status_code, 403)
        self.post_json(reverse("api_room_join", args=[match.id]))
        self.as_user(self.deniz)
        self.assertEqual(self.post_json(reverse("api_room_cancel", args=[match.id])).status_code, 409)

    def test_room_detail_access(self):
        match = self.create_room(self.deniz)
        self.assertEqual(self.client.get(reverse("api_room_detail", args=[match.id])).json(), {"status": "waiting"})
        self.as_user(self.ece)
        self.assertEqual(self.client.get(reverse("api_room_detail", args=[match.id])).status_code, 404)
        self.as_user(self.kaan)
        self.post_json(reverse("api_room_join", args=[match.id]))
        self.as_user(self.deniz)
        data = self.client.get(reverse("api_room_detail", args=[match.id])).json()
        self.assertEqual(data["status"], "active")
        self.assertEqual(data["match_url"], reverse("match", args=[match.id]))


class PageTests(ApiTestCase):
    def test_lobby_lists_challenges_and_time_limits(self):
        self.as_user(self.deniz)
        resp = self.client.get(reverse("lobby"))
        self.assertContains(resp, "Ülke Bulmaca")
        self.assertContains(resp, "20 sn")
        self.assertContains(resp, "45 sn")

    def test_room_page_host_only_and_redirects_when_active(self):
        match = self.create_room(self.deniz)
        self.assertEqual(self.client.get(reverse("room_wait", args=[match.id])).status_code, 200)
        self.as_user(self.kaan)
        self.assertEqual(self.client.get(reverse("room_wait", args=[match.id])).status_code, 404)
        self.post_json(reverse("api_room_join", args=[match.id]))
        self.as_user(self.deniz)
        resp = self.client.get(reverse("room_wait", args=[match.id]))
        self.assertRedirects(resp, reverse("match", args=[match.id]))

    def test_match_page_players_only(self):
        match = self.create_room(self.deniz)
        self.as_user(self.kaan)
        self.post_json(reverse("api_room_join", args=[match.id]))
        self.assertContains(self.client.get(reverse("match", args=[match.id])), "deniz")
        self.as_user(self.ece)
        self.assertEqual(self.client.get(reverse("match", args=[match.id])).status_code, 404)
