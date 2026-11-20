"""Test doubles for the two interfaces. FakeProvider holds one task with a known truth, so tests can
check that the truth never reaches the model before submission."""
from tutor.models import Completion

TRUTH = 24760
CORRECT_BOX = "The fee is borrowed too, and interest is charged on it"


class FakeProvider:
    def __init__(self, submitted: bool = False, passages=None):
        self.submitted = submitted
        self.passages = passages if passages is not None else [
            {"chunk_id": "f4.c1", "body": "RRSO (APR) includes the fee and the insurance.", "url": "https://example.org/rrso"}]

    def task_public(self, task_id):
        return {"id": task_id, "brief": "Ewa borrows 20,000 PLN for 36 months with an 8% fee.",
                "reasons": [CORRECT_BOX, "The bank has a nice app"]}

    def reveal(self, attempt_id):
        if not self.submitted:
            return None
        return {"truth": TRUTH, "reasons": [{"text": CORRECT_BOX, "weight": 1.0, "explain": "Fees are credited."}]}

    def task_secrets(self, task_id):
        return {"strings": [CORRECT_BOX], "numbers": [TRUTH]}

    def profile_aggregates(self, user_id):
        return {"age_band": "25-39", "goal": "first investment", "mastery": {"F4": 0.4}}

    def search_kb(self, node, query, k):
        return self.passages[:k]

    def stored_explanation(self, key, mode):
        return f"stored explanation for {key}"


class ScriptedLLM:
    """Returns the given texts in order and records every call."""

    def __init__(self, *texts):
        self.texts = list(texts)
        self.calls = []

    def complete(self, role, messages, json_schema, max_tokens, contains_user_data):
        self.calls.append({"role": role, "messages": messages, "contains_user_data": contains_user_data})
        return Completion(text=self.texts.pop(0), model="fake", tokens_in=10, tokens_out=5, latency_ms=1)
