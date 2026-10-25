import random

from .base import Challenge

OPTION_COUNT = 4


class CountryMapChallenge(Challenge):
    key = "country_map"
    label = "Ülke Bulmaca"

    def generate_rounds(self, count):
        from game.models import Country  # imported lazily: models import the registry

        pool = list(Country.objects.filter(is_active=True))
        if count > len(pool):
            raise ValueError("Not enough active countries for this many rounds.")
        rounds = []
        for target in random.sample(pool, count):
            same = [c for c in pool if c.continent == target.continent and c.pk != target.pk]
            others = [c for c in pool if c.continent != target.continent]
            distractors = random.sample(same, min(OPTION_COUNT - 1, len(same)))
            distractors += random.sample(others, OPTION_COUNT - 1 - len(distractors))
            options = [target.name_tr] + [c.name_tr for c in distractors]
            random.shuffle(options)
            rounds.append(({"iso2": target.pk, "options": options}, {"answer": target.name_tr, "iso2": target.pk}))
        return rounds

    def check_answer(self, answer_key, value):
        return value == answer_key.get("answer")
