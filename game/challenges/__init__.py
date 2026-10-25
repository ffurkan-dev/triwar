from .country_map import CountryMapChallenge

REGISTRY = {challenge.key: challenge for challenge in (CountryMapChallenge(),)}
