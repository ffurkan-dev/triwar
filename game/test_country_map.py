import json
import re

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from .challenges import REGISTRY
from .models import Country

SVG_IDS = set(re.findall(r'<path id="(\w+)"', (settings.BASE_DIR / "static" / "maps" / "world.svg").read_text()))


class CountryDataTests(TestCase):
    fixtures = ["countries"]

    def test_every_active_country_is_on_the_map(self):
        active = set(Country.objects.filter(is_active=True).values_list("iso2", flat=True))
        self.assertGreaterEqual(len(active), 100)
        self.assertFalse(active - SVG_IDS)

    def test_codes_missing_from_natural_earth_iso_a2_are_present(self):
        for iso2, name in (("FR", "Fransa"), ("NO", "Norveç")):
            self.assertEqual(Country.objects.get(pk=iso2).name_tr, name)
            self.assertIn(iso2, SVG_IDS)
            self.assertTrue(Country.objects.get(pk=iso2).is_active)


class CountryMapChallengeTests(TestCase):
    fixtures = ["countries"]

    def setUp(self):
        self.challenge = REGISTRY["country_map"]

    def test_rounds_are_unique_with_four_options_including_answer(self):
        for _ in range(5):
            rounds = self.challenge.generate_rounds(20)
            self.assertEqual(len(rounds), 20)
            self.assertEqual(len({key["iso2"] for _, key in rounds}), 20)
            for payload, key in rounds:
                self.assertEqual(len(payload["options"]), 4)
                self.assertEqual(len(set(payload["options"])), 4)
                self.assertIn(key["answer"], payload["options"])
                self.assertEqual(payload["iso2"], key["iso2"])
                self.assertNotIn("answer", payload)

    def test_distractors_prefer_same_continent(self):
        continents = dict(Country.objects.values_list("name_tr", "continent"))
        for payload, key in self.challenge.generate_rounds(30):
            target = continents[key["answer"]]
            same = sum(continents[o] == target for o in payload["options"])
            available = Country.objects.filter(continent=target, is_active=True).count()
            self.assertGreaterEqual(same, min(4, available))

    def test_check_answer(self):
        key = {"answer": "Peru", "iso2": "PE"}
        self.assertTrue(self.challenge.check_answer(key, "Peru"))
        self.assertFalse(self.challenge.check_answer(key, "Bolivya"))

    def test_too_many_rounds(self):
        with self.assertRaises(ValueError):
            self.challenge.generate_rounds(10_000)


class PracticeTests(TestCase):
    fixtures = ["countries"]

    def setUp(self):
        self.client.force_login(User.objects.create_user(email="a@example.com", username="aaa", password="x"))

    def test_page_inlines_map(self):
        resp = self.client.get(reverse("practice"))
        self.assertContains(resp, 'id="FR"')

    def test_question_does_not_leak_answer_and_answer_is_checked(self):
        data = self.client.get(reverse("api_practice_question")).json()
        self.assertEqual(set(data), {"payload"})
        self.assertEqual(set(data["payload"]), {"iso2", "options"})
        iso2 = data["payload"]["iso2"]
        right = Country.objects.get(pk=iso2).name_tr
        resp = self.client.post(reverse("api_practice_answer"), json.dumps({"value": right}), content_type="application/json")
        self.assertEqual(resp.json(), {"correct": True, "answer": right})
        # the question is consumed
        resp = self.client.post(reverse("api_practice_answer"), json.dumps({"value": right}), content_type="application/json")
        self.assertEqual(resp.status_code, 409)

    def test_wrong_answer(self):
        data = self.client.get(reverse("api_practice_question")).json()["payload"]
        wrong = next(o for o in data["options"] if o != Country.objects.get(pk=data["iso2"]).name_tr)
        resp = self.client.post(reverse("api_practice_answer"), json.dumps({"value": wrong}), content_type="application/json")
        self.assertFalse(resp.json()["correct"])

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("api_practice_question")).status_code, 401)
        self.assertEqual(self.client.get(reverse("practice")).status_code, 302)
