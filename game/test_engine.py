import json
from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User

from . import engine
from .models import Answer, Match

T0 = timezone.now().replace(microsecond=0)


def sec(n):
    return timedelta(seconds=n)


class EngineTestCase(TestCase):
    fixtures = ["countries"]

    def setUp(self):
        self.host = User.objects.create_user(email="h@example.com", username="host", password="x")
        self.guest = User.objects.create_user(email="g@example.com", username="guest", password="x")
        self.match = Match.objects.create(
            host=self.host, guest=self.guest, challenge_type="country_map", time_limit=20,
            status=Match.Status.ACTIVE, started_at=T0, total_rounds=3,
        )
        engine.start_match(self.match, T0)

    def rnd(self, index=None):
        return self.match.rounds.get(index=self.match.current_round if index is None else index)

    def answer(self, user, now, correct=True, index=None):
        engine.advance(self.match, now - sec(1))  # the client only sees the current round after a poll
        rnd = self.rnd(index)
        if correct:
            value = rnd.answer_key["answer"]
        else:
            value = next(o for o in rnd.payload["options"] if o != rnd.answer_key["answer"])
        return engine.submit_answer(self.match, user, rnd.index, value, now)


class RoundFlowTests(EngineTestCase):
    def test_rounds_generated_and_first_starts_after_countdown(self):
        rounds = list(self.match.rounds.all())
        self.assertEqual(len(rounds), 3)
        self.assertEqual(rounds[0].started_at, T0 + sec(3))
        self.assertEqual(rounds[0].deadline, T0 + sec(23))
        self.assertIsNone(rounds[1].started_at)

    def test_answer_before_round_starts_rejected(self):
        with self.assertRaises(engine.EngineError):
            self.answer(self.host, T0 + sec(1))

    def test_both_answers_close_round_then_next_starts_after_reveal(self):
        self.answer(self.host, T0 + sec(5))
        self.assertIsNone(self.rnd().closed_at)
        self.answer(self.guest, T0 + sec(8))
        first = self.rnd(0)
        self.assertEqual(first.closed_at, T0 + sec(8))
        engine.advance(self.match, T0 + sec(10))  # still revealing
        self.assertEqual(self.match.current_round, 0)
        engine.advance(self.match, T0 + sec(11))
        self.assertEqual(self.match.current_round, 1)
        nxt = self.rnd()
        self.assertEqual(nxt.started_at, T0 + sec(11))
        self.assertEqual(nxt.deadline, T0 + sec(31))

    def test_deadline_closes_round_without_answers(self):
        engine.advance(self.match, T0 + sec(22))
        self.assertIsNone(self.rnd().closed_at)
        engine.advance(self.match, T0 + sec(23))
        self.assertEqual(self.rnd(0).closed_at, T0 + sec(23))
        self.assertEqual(engine.scores(self.match)[self.host.pk]["score"], 0)
        engine.advance(self.match, T0 + sec(26))
        self.assertEqual(self.match.current_round, 1)

    def test_late_answer_rejected_but_network_tolerance_allowed(self):
        self.answer(self.host, T0 + sec(23.5))  # within the 1s tolerance
        with self.assertRaises(engine.EngineError) as ctx:
            self.answer(self.guest, T0 + sec(24.5))
        self.assertEqual(ctx.exception.status, 409)
        engine.advance(self.match, T0 + sec(26))
        self.assertEqual(self.rnd(0).closed_at, T0 + sec(23))
        self.assertEqual(Answer.objects.count(), 1)

    def test_duplicate_answer_rejected(self):
        self.answer(self.host, T0 + sec(5))
        with self.assertRaises(engine.EngineError) as ctx:
            self.answer(self.host, T0 + sec(6))
        self.assertEqual(ctx.exception.status, 409)
        self.assertEqual(Answer.objects.count(), 1)

    def test_wrong_round_index_and_invalid_value_rejected(self):
        with self.assertRaises(engine.EngineError):
            engine.submit_answer(self.match, self.host, 2, "x", T0 + sec(5))
        with self.assertRaises(engine.EngineError) as ctx:
            engine.submit_answer(self.match, self.host, 0, "Atlantis", T0 + sec(5))
        self.assertEqual(ctx.exception.status, 400)

    def test_response_time_recorded(self):
        answer = self.answer(self.host, T0 + sec(5.5))
        self.assertEqual(answer.response_ms, 2500)


class FinishTests(EngineTestCase):
    def play_round(self, start, host_correct, guest_correct, host_at=1, guest_at=2):
        self.answer(self.host, start + sec(host_at), host_correct)
        self.answer(self.guest, start + sec(guest_at), guest_correct)

    def test_match_finishes_with_higher_score_winning(self):
        t = T0 + sec(3)
        for i in range(3):
            self.play_round(t, True, i == 0)  # host 3, guest 1
            t += sec(2 + 3)
        engine.advance(self.match, t)  # a poll after the last reveal
        self.match.refresh_from_db()
        self.assertEqual(self.match.status, Match.Status.FINISHED)
        self.assertEqual(self.match.winner, self.host)
        self.assertEqual(self.match.finished_at, T0 + sec(3 + 2 + 3 + 2 + 3 + 2 + 3))

    def test_tie_broken_by_total_time_of_correct_answers(self):
        t = T0 + sec(3)
        for i in range(3):
            self.play_round(t, True, True, host_at=3, guest_at=2)  # guest always faster
            t += sec(3 + 3)
        engine.advance(self.match, t)
        self.match.refresh_from_db()
        self.assertEqual(self.match.winner, self.guest)

    def test_exact_tie_is_a_draw(self):
        t = T0 + sec(3)
        for i in range(3):
            self.play_round(t, True, True, host_at=2, guest_at=2)
            t += sec(2 + 3)
        engine.advance(self.match, t)
        self.match.refresh_from_db()
        self.assertEqual(self.match.status, Match.Status.FINISHED)
        self.assertIsNone(self.match.winner)

    def test_wrong_answers_do_not_count_for_tie_break_time(self):
        t = T0 + sec(3)
        self.play_round(t, True, False, host_at=9, guest_at=1)
        self.assertEqual(engine.scores(self.match)[self.guest.pk], {"score": 0, "ms": 0})

    def test_state_poll_long_after_catches_up_and_finishes(self):
        engine.advance(self.match, T0 + sec(1000))
        self.match.refresh_from_db()
        self.assertEqual(self.match.status, Match.Status.FINISHED)
        self.assertIsNone(self.match.winner)

    def test_answer_after_finish_rejected(self):
        engine.advance(self.match, T0 + sec(1000))
        with self.assertRaises(engine.EngineError):
            engine.submit_answer(self.match, self.host, 2, "x", T0 + sec(1001))


class StateApiTests(EngineTestCase):
    def get_state(self, user, now):
        self.client.force_login(user)
        with mock.patch("django.utils.timezone.now", return_value=now):
            return self.client.get(reverse("api_match_state", args=[self.match.id])).json()

    def post_answer(self, user, now, index, value):
        self.client.force_login(user)
        with mock.patch("django.utils.timezone.now", return_value=now):
            return self.client.post(
                reverse("api_match_answer", args=[self.match.id]),
                json.dumps({"round_index": index, "value": value}),
                content_type="application/json",
            )

    def test_countdown_hides_question(self):
        data = self.get_state(self.host, T0 + sec(1))
        self.assertEqual(data["round"]["phase"], "countdown")
        self.assertIsNone(data["round"]["payload"])
        self.assertIsNone(data["reveal"])

    def test_question_phase_does_not_leak_correct_answer(self):
        key = self.rnd(0).answer_key
        for user in (self.host, self.guest):
            resp_text = json.dumps(self.get_state(user, T0 + sec(5)), ensure_ascii=False)
            data = json.loads(resp_text)
            self.assertEqual(data["round"]["phase"], "question")
            self.assertIsNone(data["reveal"])
            self.assertNotIn("answer", data["round"]["payload"])
            self.assertNotIn("answer_key", resp_text)
            self.assertNotIn('"answer"', resp_text)
        # even after the opponent answered correctly, the other side sees only a flag
        self.post_answer(self.guest, T0 + sec(6), 0, key["answer"])
        data = self.get_state(self.host, T0 + sec(7))
        self.assertTrue(data["round"]["opponent_answered"])
        self.assertIsNone(data["round"]["my_answer"])
        self.assertIsNone(data["reveal"])
        self.assertEqual(data["players"]["opponent"]["score"], 0)  # scores count closed rounds only

    def test_reveal_after_both_answered_shows_answers_and_scores(self):
        key = self.rnd(0).answer_key
        self.post_answer(self.host, T0 + sec(5), 0, key["answer"])
        wrong = next(o for o in self.rnd(0).payload["options"] if o != key["answer"])
        self.post_answer(self.guest, T0 + sec(6), 0, wrong)
        data = self.get_state(self.host, T0 + sec(7))
        self.assertEqual(data["round"]["phase"], "reveal")
        self.assertEqual(data["reveal"]["answer"], key["answer"])
        self.assertEqual(data["reveal"]["answers"]["me"], {"value": key["answer"], "correct": True})
        self.assertEqual(data["reveal"]["answers"]["opponent"], {"value": wrong, "correct": False})
        self.assertEqual(data["players"]["me"]["score"], 1)
        self.assertEqual(data["players"]["opponent"]["score"], 0)
        other = self.get_state(self.guest, T0 + sec(7))
        self.assertEqual(other["players"]["me"]["score"], 0)
        self.assertEqual(other["players"]["opponent"]["score"], 1)

    def test_players_only_and_finished_state_has_result_url(self):
        outsider = User.objects.create_user(email="o@example.com", username="outsider", password="x")
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(reverse("api_match_state", args=[self.match.id])).status_code, 404)
        data = self.get_state(self.host, T0 + sec(1000))
        self.assertEqual(data["status"], "finished")
        self.assertEqual(data["result_url"], reverse("match_result", args=[self.match.id]))
        self.assertIsNone(data["round"])

    def test_answer_api_errors(self):
        self.assertEqual(self.post_answer(self.host, T0 + sec(5), 0, "Atlantis").status_code, 400)
        value = self.rnd(0).answer_key["answer"]
        self.assertEqual(self.post_answer(self.host, T0 + sec(5), 0, value).status_code, 200)
        self.assertEqual(self.post_answer(self.host, T0 + sec(6), 0, value).status_code, 409)
        self.assertEqual(self.post_answer(self.guest, T0 + sec(30), 0, value).status_code, 409)

    def test_result_page(self):
        engine.advance(self.match, T0 + sec(1000))
        self.client.force_login(self.host)
        resp = self.client.get(reverse("match_result", args=[self.match.id]))
        self.assertContains(resp, "Berabere")
        self.assertRedirects(self.client.get(reverse("match", args=[self.match.id])), reverse("match_result", args=[self.match.id]))
