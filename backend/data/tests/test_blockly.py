import pytest

from common import AttemptError
from hard.blockly import (ROOT, ConversionError, block_definitions, program_to_workspace, toolbox,
                          workspace_to_program)
from hard.build import build, load_tasks
from hard.task import score


@pytest.fixture(scope="module")
def s1():
    rec = {tid: rec for tid, rec, _, _ in build()}["s1.h1"]
    task = [t for t in load_tasks() if t["id"] == "s1.h1"][0]
    return rec, task


def test_every_content_program_survives_the_round_trip(s1):
    # The app sends Blockly JSON; if the converter changed a program, the user's rule would be scored wrongly.
    _, task = s1
    programs = [task["reference_program"], task["starter_program"]]
    programs += [b["program"] for b in task["known_bad_programs"] + task["baseline_bots"]]
    for p in programs:
        assert workspace_to_program(program_to_workspace(p)) == p


def test_definitions_and_toolbox_match_the_palette(s1):
    rec, task = s1
    defs = {d["type"]: d for d in rec["question"]["blockly"]["blocks"]}
    assert ROOT in defs and {"fq_" + b for b in task["palette"]} <= set(defs)
    assert [o[1] for o in defs["fq_var"]["args0"][0]["options"]] == task["vars"]
    assert defs["fq_if_else"]["args0"][0]["check"] == "Boolean" and defs["fq_invest"]["args0"][0]["check"] == "Number"
    listed = {b["type"] for c in rec["question"]["blockly"]["toolbox"]["contents"] for b in c["contents"]}
    assert listed <= set(defs)


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


def test_score_accepts_a_workspace(s1):
    rec, task = s1
    assert score(rec, program_to_workspace(task["reference_program"]))["points"] == score(rec, task["reference_program"])["points"]
    with pytest.raises(AttemptError):
        score(rec, {"blocks": {"blocks": []}})


def test_toolbox_skips_blocks_outside_the_palette():
    tb = toolbox(["if_else", "invest"], ["cash"])
    types = [b["type"] for c in tb["contents"] for b in c["contents"]]
    assert "fq_pay_debt" not in types and types.count("fq_var") == 1
