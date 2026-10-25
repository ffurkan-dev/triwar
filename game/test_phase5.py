import json
import re
from datetime import timedelta
from unittest import mock

from django.test import Client, TestCase
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from accounts.models import User

from . import engine
from .models import Match, user_stats

T0 = timezone.now().replace(microsecond=0)


def sec(n):
    return timedelta(seconds=n)


def make_user(name):
    return User.objects.create_user(email=f"{name}@example.com", username=name, password="x")


class Phase5TestCase(TestCase):
    fixtures = ["countries"]

    def setUp(self):
        self.host = make_user("host")
        self.guest = make_user("guest")

    def active_match(self):
        match = Match.objects.create(
            host=self.host, guest=self.guest, challenge_type="country_map", time_limit=20,
            status=Match.Status.ACTIVE, started_at=T0, total_rounds=3,
        )
        engine.start_match(match, T0)
        return match

    def at(self, now, method, url, user=None, data=None):
        if user:
            self.client.force_login(user)
        with mock.patch("django.utils.timezone.now", return_value=now):
            if method == "get":
                return self.client.get(url)
            return self.client.post(url, json.dumps(data or {}), content_type="application/json")


class AbandonTests(Phase5TestCase):
    def state(self, match, user, now):
        return self.at(now, "get", reverse("api_match_state", args=[match.id]), user).json()

    def test_active_players_are_not_forfeited(self):
        match = self.active_match()
        self.assertEqual(self.state(match, self.host, T0 + sec(25))["status"], "active")
        self.assertEqual(self.state(match, self.guest, T0 + sec(28))["status"], "active")
        self.assertEqual(self.state(match, self.host, T0 + sec(40))["status"], "active")

    def test_player_unseen_for_30s_forfeits(self):
        match = self.active_match()
        self.state(match, self.guest, T0 + sec(10))
        data = self.state(match, self.host, T0 + sec(41))  # guest last seen at T0+10
        self.assertEqual(data["status"], "finished")
        self.assertEqual(data["end_reason"], "abandoned")
        match.refresh_from_db()
        self.assertEqual(match.winner, self.host)
        self.assertEqual(match.finished_at, T0 + sec(41))

    def test_just_under_30s_is_fine(self):
        match = self.active_match()
        self.assertEqual(self.state(match, self.host, T0 + sec(30))["status"], "active")

    def test_result_page_wording_for_both_sides(self):
        match = self.active_match()
        self.state(match, self.host, T0 + sec(60))
        winner_page = self.at(T0 + sec(61), "get", reverse("match_result", args=[match.id]), self.host)
        self.assertContains(winner_page, "Rakip ayrıldı")
        loser_page = self.at(T0 + sec(61), "get", reverse("match_result", args=[match.id]), self.guest)
        self.assertContains(loser_page, "hükmen kaybettin")

    def test_leaving_counts_as_a_loss(self):
        match = self.active_match()
        self.state(match, self.host, T0 + sec(60))
        self.assertEqual(user_stats(self.host), {"wins": 1, "losses": 0, "draws": 0})
        self.assertEqual(user_stats(self.guest), {"wins": 0, "losses": 1, "draws": 0})

    def test_answers_keep_a_player_alive(self):
        match = self.active_match()
        rnd = match.rounds.get(index=0)
        self.at(T0 + sec(20), "post", reverse("api_match_answer", args=[match.id]), self.guest,
                {"round_index": 0, "value": rnd.payload["options"][0]})
        self.assertEqual(self.state(match, self.host, T0 + sec(45))["status"], "active")


class StaleRoomTests(Phase5TestCase):
    def make_room(self):
        return Match.objects.create(host=self.host, challenge_type="country_map", time_limit=20)

    def test_old_waiting_rooms_are_cancelled_when_listing(self):
        room = self.make_room()
        Match.objects.filter(pk=room.pk).update(created_at=T0 - timedelta(minutes=11))
        fresh = Match.objects.create(host=self.guest, challenge_type="country_map", time_limit=45)
        viewer = make_user("viewer")
        data = self.at(T0, "get", reverse("api_rooms"), viewer).json()
        self.assertEqual([r["id"] for r in data["rooms"]], [str(fresh.id)])
        room.refresh_from_db()
        self.assertEqual(room.status, Match.Status.CANCELLED)

    def test_room_younger_than_ttl_stays(self):
        room = self.make_room()
        Match.objects.filter(pk=room.pk).update(created_at=T0 - timedelta(minutes=9))
        viewer = make_user("viewer")
        self.assertEqual(len(self.at(T0, "get", reverse("api_rooms"), viewer).json()["rooms"]), 1)

    def test_cannot_join_stale_room_and_host_sees_cancelled(self):
        room = self.make_room()
        Match.objects.filter(pk=room.pk).update(created_at=T0 - timedelta(minutes=11))
        resp = self.at(T0, "post", reverse("api_room_join", args=[room.id]), self.guest)
        self.assertEqual(resp.status_code, 409)
        data = self.at(T0, "get", reverse("api_room_detail", args=[room.id]), self.host).json()
        self.assertEqual(data["status"], "cancelled")

    def test_stale_room_does_not_block_creating_a_new_one(self):
        room = self.make_room()
        Match.objects.filter(pk=room.pk).update(created_at=T0 - timedelta(minutes=11))
        resp = self.at(T0, "post", reverse("api_rooms"), self.host, {"challenge_type": "country_map", "time_limit": 20})
        self.assertEqual(resp.status_code, 201)

    def test_beacon_style_cancel_with_form_encoded_csrf(self):
        room = self.make_room()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.host)
        page = client.get(reverse("lobby")).content.decode()
        token = re.search(r'name="csrf-token" content="([^"]+)"', page).group(1)
        resp = client.post(reverse("api_room_cancel", args=[room.id]), {"csrfmiddlewaretoken": token})
        self.assertEqual(resp.status_code, 200)
        room.refresh_from_db()
        self.assertEqual(room.status, Match.Status.CANCELLED)
        self.assertEqual(client.post(reverse("api_rooms"), "{}", content_type="application/json").status_code, 403)


class RateLimitTests(Phase5TestCase):
    def test_room_creation_is_rate_limited(self):
        self.client.force_login(self.host)
        payload = json.dumps({"challenge_type": "country_map", "time_limit": 20})
        for _ in range(5):
            resp = self.client.post(reverse("api_rooms"), payload, content_type="application/json")
            self.assertEqual(resp.status_code, 201)
            self.client.post(reverse("api_room_cancel", args=[resp.json()["id"]]))
        resp = self.client.post(reverse("api_rooms"), payload, content_type="application/json")
        self.assertEqual(resp.status_code, 429)

    def test_limit_expires(self):
        self.client.force_login(self.host)
        payload = json.dumps({"challenge_type": "country_map", "time_limit": 20})
        for _ in range(5):
            resp = self.client.post(reverse("api_rooms"), payload, content_type="application/json")
            self.client.post(reverse("api_room_cancel", args=[resp.json()["id"]]))
        Match.objects.update(created_at=timezone.now() - timedelta(minutes=2))
        resp = self.client.post(reverse("api_rooms"), payload, content_type="application/json")
        self.assertEqual(resp.status_code, 201)


class StatsAndSummaryTests(Phase5TestCase):
    def finished_match(self, winner):
        match = self.active_match()
        engine.advance(match, T0 + sec(1000))
        Match.objects.filter(pk=match.pk).update(winner=winner)
        return match

    def test_user_stats_counts(self):
        self.finished_match(self.host)
        self.finished_match(self.host)
        self.finished_match(None)
        self.assertEqual(user_stats(self.host), {"wins": 2, "losses": 0, "draws": 1})
        self.assertEqual(user_stats(self.guest), {"wins": 0, "losses": 2, "draws": 1})

    def test_stats_in_lobby_and_room_list(self):
        self.finished_match(self.host)
        self.client.force_login(self.host)
        self.assertContains(self.client.get(reverse("lobby")), "1 G")
        Match.objects.create(host=self.host, challenge_type="country_map", time_limit=20)
        self.client.force_login(self.guest)
        rooms = self.client.get(reverse("api_rooms")).json()["rooms"]
        self.assertEqual(rooms[0]["host_stats"], {"wins": 1, "losses": 0, "draws": 0})

    def test_result_page_lists_rounds_with_countries_and_answers(self):
        match = self.active_match()
        rnd = match.rounds.get(index=0)
        engine.submit_answer(match, self.host, 0, rnd.answer_key["answer"], T0 + sec(5))
        engine.advance(match, T0 + sec(1000))
        self.client.force_login(self.host)
        page = self.client.get(reverse("match_result", args=[match.id])).content.decode()
        self.assertIn("Tur tur özet", page)
        self.assertEqual(page.count("round-item"), 3)
        self.assertIn(rnd.answer_key["answer"], page)
        self.assertIn("Cevap vermedi", page)


class ErrorPageTests(TestCase):
    def test_404_page(self):
        resp = self.client.get("/bu-sayfa-yok/")
        self.assertContains(resp, "Aradığın sayfa bulunamadı", status_code=404)

    def test_500_template_renders_standalone(self):
        self.assertIn("Bir şeyler ters gitti", render_to_string("500.html"))
