from .base import Challenge


class CountryMapChallenge(Challenge):
    key = "country_map"
    label = "Ülke Bulmaca"

    def generate_rounds(self, count):
        # Filled in with the country data in phase 3.
        return []

    def check_answer(self, answer_key, value):
        return value == answer_key.get("answer")
