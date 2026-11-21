from analytics.signals import DENYLIST, adviser_signals
from tutor.checks import check_advice


def test_signals_follow_the_rules_and_never_name_a_product():
    learners = [
        {"pseudo": "a", "survey": {"goal": "first_investment", "horizon": "over_10"}, "done": {"I4", "I5", "P1"}, "confidence": 4},
        {"pseudo": "b", "survey": {"goal": "buffer", "horizon": "under_3", "buffer": "none"}, "done": {"S1", "I2"}},
        {"pseudo": "c", "survey": {"goal": "retirement", "horizon": "over_10", "products": ["consumer_loan"]}, "done": {"F1", "P2", "I5", "P1"}},
        {"pseudo": "d", "survey": {"goal": "home", "horizon": "3_10"}, "done": set()},
    ]
    sig = adviser_signals(learners)
    topics = {(x["pseudo"], x["topic"]) for x in sig}
    assert ("a", "index funds") in topics and ("b", "an emergency fund and a savings account") in topics
    assert ("b", "deposits and retail bonds") in topics and ("c", "retirement accounts such as IKE and IKZE") in topics
    assert not any(x["pseudo"] == "d" for x in sig)
    assert sum(1 for x in sig if x["pseudo"] == "a" and x["topic"] == "index funds") == 1
    assert "confidence 4/5" in next(x["text"] for x in sig if x["pseudo"] == "a")
    for x in sig:
        assert check_advice(x["text"], DENYLIST) == [], x["text"]
