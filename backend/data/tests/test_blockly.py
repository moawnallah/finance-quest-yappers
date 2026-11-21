import pytest

from common import AttemptError
from hard.blockly import (ROOT, ConversionError, block_definitions, program_to_workspace, toolbox,
                          workspace_to_program)
from hard.dsl import OWN_VAR_BLOCKS
from hard.build import build, load_tasks
from hard.task import score


@pytest.fixture(scope="module")
def p1():
    rec = {tid: rec for tid, rec, _, _ in build()}["p1.h1"]
    task = [t for t in load_tasks() if t["id"] == "p1.h1"][0]
    return rec, task


def test_every_content_program_survives_the_round_trip():
    # The app sends Blockly JSON; if the converter changed a program, the user's rule would be scored wrongly.
    programs = []
    for task in load_tasks():  # every hard task, so new blocks (e.g. rebalance) are covered
        programs += [task["reference_program"], task["starter_program"]]
        programs += [b["program"] for b in task["known_bad_programs"] + task["baseline_bots"]]
    programs.append(OWN_VARS)
    for p in programs:
        assert workspace_to_program(program_to_workspace(p)) == p


def test_definitions_and_toolbox_match_the_palette(p1):
    rec, task = p1
    defs = {d["type"]: d for d in rec["question"]["blockly"]["blocks"]}
    ours = {"fq_" + b for b in task["palette"] if b not in OWN_VAR_BLOCKS}   # own variables are Blockly's built-ins
    assert ROOT in defs and ours <= set(defs)
    assert [o[1] for o in defs["fq_var"]["args0"][0]["options"]] == task["vars"]
    assert defs["fq_if_else"]["args0"][0]["check"] == "Boolean" and defs["fq_invest_in"]["args0"][0]["check"] == "Number"
    assert [o[1] for o in defs["fq_invest_in"]["args0"][1]["options"]] == list(task["assets"])
    categories = rec["question"]["blockly"]["toolbox"]["contents"]
    listed = {b["type"] for c in categories for b in c.get("contents", [])}
    assert listed <= set(defs) and {"kind": "category", "name": "My variables", "custom": "VARIABLE"} in categories


def test_message_slots_match_arguments():
    # Blockly rejects a definition whose %n placeholders do not match args0.
    for d in block_definitions(["if_else", "compare", "and", "not", "math", "number", "invest"], ["cash"]):
        n = len(d["args0"])
        assert all(f"%{i}" in d["message0"] for i in range(1, n + 1)) and f"%{n + 1}" not in d["message0"]


@pytest.mark.parametrize("workspace, message", [
    ({"blocks": {"blocks": []}}, "exactly one"),
    ({"blocks": {"blocks": [{"type": ROOT}, {"type": ROOT}]}}, "exactly one"),
    ({"blocks": {"blocks": [{"type": ROOT, "inputs": {"DO": {"block": {"type": "fq_invest"}}}}]}}, "empty slot"),
    ({"blocks": {"blocks": [{"type": ROOT, "inputs": {"DO": {"block": {"type": "controls_if"}}}}]}}, "unknown block"),
])
def test_bad_workspaces(workspace, message):
    with pytest.raises(ConversionError, match=message):
        workspace_to_program(workspace)


def test_score_accepts_a_workspace(p1):
    rec, task = p1
    assert score(rec, program_to_workspace(task["reference_program"]))["points"] == score(rec, task["reference_program"])["points"]
    with pytest.raises(AttemptError):
        score(rec, {"blocks": {"blocks": []}})


def test_toolbox_skips_blocks_outside_the_palette():
    tb = toolbox(["if_else", "invest"], ["cash"])
    types = [b["type"] for c in tb["contents"] for b in c["contents"]]
    assert "fq_pay_debt" not in types and types.count("fq_var") == 1


OWN_VARS = {"every_month": [
    {"block": "change_var", "name": "saved", "value": {"block": "number", "value": 100}},
    {"block": "if", "if": {"block": "compare", "op": ">", "left": {"block": "my_var", "name": "saved"},
                           "right": {"block": "number", "value": 500}},
     "then": [{"block": "invest_in", "amount": {"block": "var", "name": "cash"}, "asset": "fund"},
              {"block": "set_var", "name": "saved", "value": {"block": "number", "value": 0}}]}]}


def test_blockly_variables_as_the_app_saves_them():
    # Blockly stores a variable by id with the names in a separate list; reading the id as the name would break every rule.
    ws = {"variables": [{"name": "saved", "id": "Xy#1"}],
          "blocks": {"blocks": [{"type": ROOT, "inputs": {"DO": {"block": {
              "type": "math_change", "fields": {"VAR": {"id": "Xy#1"}},
              "inputs": {"DELTA": {"shadow": {"type": "math_number", "fields": {"NUM": 100}}}},
              "next": {"block": {"type": "fq_invest_in", "fields": {"ASSET": "fund"},
                                 "inputs": {"AMOUNT": {"block": {"type": "variables_get",
                                                                 "fields": {"VAR": {"id": "Xy#1"}}}}}}}}}}}]}}
    assert workspace_to_program(ws) == {"every_month": [
        {"block": "change_var", "name": "saved", "value": {"block": "number", "value": 100}},
        {"block": "invest_in", "amount": {"block": "my_var", "name": "saved"}, "asset": "fund"}]}


def test_number_slots_start_with_a_typed_number():
    # Typing a number into a slot is the Scratch habit we promised; the toolbox must carry the shadow for it.
    tb = toolbox(["invest_in", "compare"], [])
    entries = {b["type"]: b for c in tb["contents"] for b in c.get("contents", [])}
    assert entries["fq_invest_in"]["inputs"]["AMOUNT"]["shadow"]["type"] == "fq_number"
    assert set(entries["fq_compare"]["inputs"]) == {"LEFT", "RIGHT"}
