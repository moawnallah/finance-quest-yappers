"""The rule layer is the first line against advice extraction and injection, and it must not block
normal learner questions. Expectations come from eval/red_team.yaml."""
from pathlib import Path

import pytest
import yaml

from tutor.rules import rule_intent

ITEMS = yaml.safe_load((Path(__file__).resolve().parents[1] / "eval" / "red_team.yaml").read_text(encoding="utf-8"))
EXPECTED_INTENT = {"advice": "advice_request", "injection": "injection"}


@pytest.mark.parametrize("item", [i for i in ITEMS if i["expect"] == "template"], ids=lambda i: i["id"])
def test_rules_catch(item):
    assert rule_intent(item["message"]) == EXPECTED_INTENT[item["category"]]


@pytest.mark.parametrize("item", [i for i in ITEMS if i["expect"] == "benign"], ids=lambda i: i["id"])
def test_rules_let_learner_questions_through(item):
    assert rule_intent(item["message"]) is None
