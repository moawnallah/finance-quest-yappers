"""The output checks are the safety layer; a regex change can silently open it. One passing and one
failing hand-written text per check."""
from tutor import checks

CONTEXT = '{"task": {"amount": "10,000 PLN", "rate": 5, "inflation": 3}} [K1] It buys what 10,194 PLN bought.'


def test_numbers_from_context_pass_in_any_format():
    text = "At 5% interest and 3% inflation, 10 000 PLN buys what about 10,194 PLN bought a year earlier."
    assert checks.check_numbers(text, CONTEXT) == []


def test_invented_number_fails():
    assert checks.check_numbers("You would end with 12,750 PLN.", CONTEXT) == ["number not in context: 12750"]


def test_small_counting_numbers_are_free():
    assert checks.check_numbers("Think about two reasons, then step 3.", "") == []


def test_advice_checks():
    assert checks.check_advice("Compare the cost sections of two KIDs first.", ["Acme Fund"]) == []
    assert "ISIN" in checks.check_advice("Consider PLXYZ1234567 for this.")
    assert any("advice phrase" in p for p in checks.check_advice("You should buy an index fund now."))
    assert any("Acme Fund" in p for p in checks.check_advice("acme fund is cheap.", ["Acme Fund"]))
    assert "ticker" in checks.check_advice("Look at GPW: PKO for this.")


def test_leak_check_catches_truth_value_and_correct_box():
    secrets = {"strings": ["The fee is borrowed too"], "numbers": [24760]}
    assert checks.check_leak("Think about what the fee does over 36 months.", secrets) == []
    assert checks.check_leak("You will pay about 24,760 PLN in total.", secrets) == ["leaks the number 24760"]
    assert checks.check_leak("Remember: the fee is borrowed too.", secrets) == ["leaks 'The fee is borrowed too'"]


def test_citations():
    assert checks.check_citations(["K1"], ["K1", "K2"]) == []
    assert checks.check_citations(["K9"], ["K1"]) == ["unknown citation 'K9'"]
    assert checks.check_citations([], ["K1"]) == ["no citation although passages were provided"]
    assert checks.check_citations([], []) == []


def test_form():
    assert checks.check_form("Short answer.", "Why?") == []
    assert checks.check_form("word " * 201, "Why?") == ["longer than 200 words"]
    assert checks.check_form("Short answer.", "") == ["no check question"]
