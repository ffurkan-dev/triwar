class Challenge:
    """Common interface every challenge type implements."""

    key: str
    label: str

    def generate_rounds(self, count: int) -> list[tuple[dict, dict]]:
        """Return `count` (payload, answer_key) pairs. No repeated questions in one match."""
        raise NotImplementedError

    def check_answer(self, answer_key: dict, value: str) -> bool:
        raise NotImplementedError
